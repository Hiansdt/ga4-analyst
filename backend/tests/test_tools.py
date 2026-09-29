import json

from fakes import FakeRunner, daily_result
from pydantic import BaseModel, Field

from analyst.core.registry import Tool, ToolOutput, ToolRegistry, TurnContext
from analyst.tools.charts import create_chart_tool
from analyst.tools.follow_ups import suggest_follow_ups_tool
from analyst.tools.queries import compiled_query_tool, run_sql_tool


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

    output = registry.run("run_sql", {"sql": "SELECT 1", "purpose": "Check"}, ctx)

    sent = json.loads(output.content)
    assert not output.is_error
    assert sent["result_id"] in ctx.results
    assert sent["total_rows"] == 30
    assert len(sent["rows"]) == 5
    assert "first 5 of 30" in sent["note"]
    assert output.display["sql"] == "SELECT 1"


def test_run_sql_failures_go_back_to_the_model():
    registry = ToolRegistry([run_sql_tool(FakeRunner(daily_result(3)), preview_rows=5)])

    output = registry.run("run_sql", {"sql": "SELECT BROKEN", "purpose": "Check"}, TurnContext())

    assert output.is_error
    assert "Syntax error" in output.content
    assert output.display == {"label": "Check", "sql": "SELECT BROKEN", "error": output.content}


def chart_registry_with_result(ctx: TurnContext) -> tuple[ToolRegistry, str]:
    registry = ToolRegistry([run_sql_tool(FakeRunner(daily_result(3)), preview_rows=2), create_chart_tool()])
    result_id = json.loads(registry.run("run_sql", {"sql": "SELECT 1", "purpose": "Check"}, ctx).content)["result_id"]
    return registry, result_id


def test_chart_uses_every_stored_row_not_the_preview():
    ctx = TurnContext()
    registry, result_id = chart_registry_with_result(ctx)

    output = registry.run(
        "create_chart", {"result_id": result_id, "type": "line", "title": "Daily", "x": "day", "y": ["events"]}, ctx
    )

    assert not output.is_error
    assert output.display == {
        "type": "line",
        "title": "Daily",
        "x": "day",
        "y": ["events"],
        "rows": [
            {"day": "2020-11-01", "events": 101},
            {"day": "2020-11-02", "events": 102},
            {"day": "2020-11-03", "events": 103},
        ],
    }


def test_chart_rejects_an_unknown_result():
    output = ToolRegistry([create_chart_tool()]).run(
        "create_chart", {"result_id": "r9", "type": "bar", "title": "T", "x": "day", "y": ["events"]}, TurnContext()
    )

    assert output.is_error
    assert "r9" in output.content


def test_chart_rejects_unknown_columns_and_lists_the_real_ones():
    ctx = TurnContext()
    registry, result_id = chart_registry_with_result(ctx)

    output = registry.run(
        "create_chart", {"result_id": result_id, "type": "bar", "title": "T", "x": "day", "y": ["revenue"]}, ctx
    )

    assert output.is_error
    assert "revenue" in output.content
    assert "events" in output.content


def test_chart_values_must_be_numeric():
    ctx = TurnContext()
    registry, result_id = chart_registry_with_result(ctx)

    output = registry.run(
        "create_chart", {"result_id": result_id, "type": "bar", "title": "T", "x": "events", "y": ["day"]}, ctx
    )

    assert output.is_error
    assert "numeric" in output.content


def test_funnel_and_pie_take_a_single_value_column():
    output = ToolRegistry([create_chart_tool()]).run(
        "create_chart", {"result_id": "r1", "type": "pie", "title": "T", "x": "day", "y": ["a", "b"]}, TurnContext()
    )

    assert output.is_error


class DaysInput(BaseModel):
    days: int = Field(ge=1)


def days_registry(runner: FakeRunner, sql: str = "SELECT day FROM t LIMIT @days") -> ToolRegistry:
    tool = compiled_query_tool(
        runner,
        name="count_days",
        description="Count days.",
        input_model=DaysInput,
        compile=lambda args: (sql, {"days": args.days}),
        label=lambda args: "Days",
        preview_rows=5,
    )
    return ToolRegistry([tool])


def test_compiled_query_runs_the_generated_sql_with_its_parameters():
    runner, ctx = FakeRunner(daily_result(3)), TurnContext()

    output = days_registry(runner).run("count_days", {"days": 3}, ctx)

    assert runner.queries == ["SELECT day FROM t LIMIT @days"]
    assert runner.params == [{"days": 3}]
    assert json.loads(output.content)["result_id"] in ctx.results
    assert output.display["sql"] == "-- @days = 3\nSELECT day FROM t LIMIT @days"


def test_compiled_query_input_errors_go_back_to_the_model_without_querying():
    runner = FakeRunner(daily_result(3))

    output = days_registry(runner).run("count_days", {"days": 0}, TurnContext())

    assert output.is_error
    assert runner.queries == []


def test_compiled_query_failures_go_back_to_the_model():
    output = days_registry(FakeRunner(daily_result(3)), sql="BROKEN").run("count_days", {"days": 1}, TurnContext())

    assert output.is_error
    assert output.display["sql"] == "-- @days = 1\nBROKEN"


def test_query_steps_carry_a_plain_language_label_for_the_user():
    registry = ToolRegistry([run_sql_tool(FakeRunner(daily_result(3)), preview_rows=5)])

    output = registry.run("run_sql", {"sql": "SELECT 1", "purpose": "Revenue by month"}, TurnContext())

    assert output.display["label"] == "Revenue by month"


def test_compiled_queries_are_labeled_from_their_input():
    tool = compiled_query_tool(
        FakeRunner(daily_result(3)),
        name="count_days",
        description="Count days.",
        input_model=DaysInput,
        compile=lambda args: ("SELECT 1", {}),
        label=lambda args: f"First {args.days} days",
        preview_rows=5,
    )

    output = ToolRegistry([tool]).run("count_days", {"days": 3}, TurnContext())

    assert output.display["label"] == "First 3 days"


def test_follow_up_suggestions_are_shown_to_the_user():
    registry = ToolRegistry([suggest_follow_ups_tool()])
    questions = ["Break down cart drop-off by device", "Compare December with January"]

    output = registry.run("suggest_follow_ups", {"questions": questions}, TurnContext())

    assert not output.is_error
    assert output.display == {"questions": questions}


def test_follow_up_suggestions_are_few_and_short():
    registry = ToolRegistry([suggest_follow_ups_tool()])

    assert registry.run("suggest_follow_ups", {"questions": ["Only one"]}, TurnContext()).is_error
    assert registry.run("suggest_follow_ups", {"questions": ["x" * 101, "Short"]}, TurnContext()).is_error
