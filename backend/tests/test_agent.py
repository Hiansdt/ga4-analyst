from fakes import FakeRunner, ScriptedModel, daily_result, text, tool_use

from ga4_agent.agent import Agent
from ga4_agent.events import TextDelta, ToolFinished, ToolStarted, TurnCompleted, TurnFailed
from ga4_agent.llm import ModelError, ModelTurn, Usage
from ga4_agent.tools import ToolRegistry, run_sql_tool


def make_agent(model: ScriptedModel, max_steps: int = 5) -> Agent:
    tools = ToolRegistry([run_sql_tool(FakeRunner(daily_result(3)), preview_rows=10)])
    return Agent(model=model, tools=tools, system_prompt="You are a test.", max_steps=max_steps)


def answer(value: str) -> ModelTurn:
    return ModelTurn(content=[text(value)], stop_reason="end_turn")


def sql_call(tool_use_id: str, sql: str) -> ModelTurn:
    return ModelTurn(content=[tool_use(tool_use_id, "run_sql", sql=sql)], stop_reason="tool_use")


def test_plain_answer_streams_text_and_completes_the_turn():
    events = list(make_agent(ScriptedModel(answer("Hello."))).run_turn([], "Hi"))

    assert events[0] == TextDelta("Hello.")
    assert events[-1] == TurnCompleted(
        [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": [text("Hello.")]}]
    )


def test_history_is_sent_before_the_new_message():
    model = ScriptedModel(answer("Still here."))
    history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": [text("Hello.")]}]

    list(make_agent(model).run_turn(history, "Again?"))

    assert model.requests[0]["messages"] == [*history, {"role": "user", "content": "Again?"}]


def test_tool_calls_run_and_their_results_go_back_in_one_user_message():
    turn = ModelTurn(
        content=[tool_use("a", "run_sql", sql="SELECT 1"), tool_use("b", "run_sql", sql="SELECT 2")],
        stop_reason="tool_use",
    )
    model = ScriptedModel(turn, answer("Done."))

    events = list(make_agent(model).run_turn([], "Two queries"))

    assert [type(e) for e in events[:4]] == [ToolStarted, ToolFinished, ToolStarted, ToolFinished]
    tool_results = model.requests[1]["messages"][-1]
    assert tool_results["role"] == "user"
    assert [r["tool_use_id"] for r in tool_results["content"]] == ["a", "b"]
    assert len(events[-1].messages) == 4


def test_failed_query_goes_back_to_the_model_so_it_can_fix_it():
    model = ScriptedModel(sql_call("a", "SELECT BROKEN"), sql_call("b", "SELECT fixed"), answer("Fixed it."))

    events = list(make_agent(model).run_turn([], "Query"))

    finished = [e for e in events if isinstance(e, ToolFinished)]
    assert [e.is_error for e in finished] == [True, False]
    [error_result] = model.requests[1]["messages"][-1]["content"]
    assert error_result["is_error"] is True
    assert "Syntax error" in error_result["content"]
    assert isinstance(events[-1], TurnCompleted)


def test_last_step_disables_tools_so_the_model_must_answer():
    model = ScriptedModel(sql_call("a", "SELECT 1"), sql_call("b", "SELECT 2"), answer("Best effort."))

    events = list(make_agent(model, max_steps=3).run_turn([], "Keep querying"))

    assert [r["allow_tools"] for r in model.requests] == [True, True, False]
    assert isinstance(events[-1], TurnCompleted)


def test_model_errors_fail_the_turn_but_keep_a_valid_history():
    model = ScriptedModel(sql_call("a", "SELECT 1"), ModelError("overloaded"))

    events = list(make_agent(model).run_turn([], "Query"))

    assert events[-2] == TurnFailed("overloaded")
    messages = events[-1].messages
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[-1]["content"][0]["type"] == "tool_result"


def test_unexpected_stop_reason_fails_the_turn_without_keeping_the_partial_reply():
    truncated = ModelTurn(content=[tool_use("a", "run_sql", sql="SELECT")], stop_reason="max_tokens")

    events = list(make_agent(ScriptedModel(truncated)).run_turn([], "Query"))

    assert isinstance(events[-2], TurnFailed)
    assert events[-1] == TurnCompleted([{"role": "user", "content": "Query"}])


def test_running_out_of_steps_without_an_answer_fails_the_turn():
    model = ScriptedModel(sql_call("a", "SELECT 1"), sql_call("b", "SELECT 2"))

    events = list(make_agent(model, max_steps=2).run_turn([], "Keep querying"))

    assert events[-2] == TurnFailed("No answer after 2 steps.")
    assert [m["role"] for m in events[-1].messages] == ["user", "assistant", "user", "assistant", "user"]


def test_token_usage_is_summed_across_steps():
    first = ModelTurn(
        content=[tool_use("a", "run_sql", sql="SELECT 1")], stop_reason="tool_use", usage=Usage(100, 10, 0, 90)
    )
    second = ModelTurn(content=[text("Done.")], stop_reason="end_turn", usage=Usage(120, 20, 90, 0))

    events = list(make_agent(ScriptedModel(first, second)).run_turn([], "Query"))

    assert events[-1].usage == Usage(220, 30, 90, 90)
