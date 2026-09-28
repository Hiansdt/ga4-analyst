import json

from fakes import FakeRunner, daily_result
from pydantic import BaseModel

from ga4_agent.tools import Tool, ToolOutput, ToolRegistry, TurnContext, run_sql_tool


class EchoInput(BaseModel):
    message: str


def echo_tool() -> Tool:
    return Tool(
        name="echo",
        description="Echo a message.",
        input_model=EchoInput,
        handler=lambda args, ctx: ToolOutput(content=args.message, display={"message": args.message}),
    )


def test_definitions_expose_json_schema_from_the_input_model():
    [definition] = ToolRegistry([echo_tool()]).definitions()

    assert definition["name"] == "echo"
    assert definition["description"] == "Echo a message."
    assert definition["input_schema"]["required"] == ["message"]


def test_runs_a_tool_with_validated_input():
    output = ToolRegistry([echo_tool()]).run("echo", {"message": "hi"}, TurnContext())

    assert output == ToolOutput(content="hi", display={"message": "hi"})


def test_invalid_input_becomes_an_error_for_the_model():
    output = ToolRegistry([echo_tool()]).run("echo", {"msg": "hi"}, TurnContext())

    assert output.is_error
    assert "message" in output.content


def test_unknown_tool_becomes_an_error_for_the_model():
    output = ToolRegistry([echo_tool()]).run("missing", {}, TurnContext())

    assert output.is_error
    assert "missing" in output.content


def test_run_sql_stores_the_result_and_shows_the_model_a_preview():
    ctx = TurnContext()
    registry = ToolRegistry([run_sql_tool(FakeRunner(daily_result(30)), preview_rows=5)])

    output = registry.run("run_sql", {"sql": "SELECT 1"}, ctx)

    sent = json.loads(output.content)
    assert not output.is_error
    assert sent["result_id"] in ctx.results
    assert sent["total_rows"] == 30
    assert len(sent["rows"]) == 5
    assert "first 5 of 30" in sent["note"]
    assert output.display["sql"] == "SELECT 1"


def test_run_sql_failures_go_back_to_the_model():
    registry = ToolRegistry([run_sql_tool(FakeRunner(daily_result(3)), preview_rows=5)])

    output = registry.run("run_sql", {"sql": "SELECT BROKEN"}, TurnContext())

    assert output.is_error
    assert "Syntax error" in output.content
    assert output.display == {"sql": "SELECT BROKEN", "error": output.content}
