"""Tool registry and the analysis tools the model can call."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from ga4_agent.sql import QueryError, QueryResult, SqlRunner


@dataclass
class TurnContext:
    """State shared by the tool calls of one turn: the query results they produced."""

    results: dict[str, QueryResult] = field(default_factory=dict)

    def store(self, result: QueryResult) -> str:
        result_id = f"r{len(self.results) + 1}"
        self.results[result_id] = result
        return result_id


@dataclass(frozen=True)
class ToolOutput:
    content: str  # what the model reads
    display: dict[str, Any]  # what the UI renders
    is_error: bool = False


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[[Any, TurnContext], ToolOutput]  # receives a validated input_model instance


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def definitions(self) -> list[dict]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_model.model_json_schema()}
            for t in self._tools.values()
        ]

    def run(self, name: str, raw_input: dict, ctx: TurnContext) -> ToolOutput:
        tool = self._tools.get(name)
        if tool is None:
            return _error(f"Unknown tool {name!r}.")
        try:
            args = tool.input_model.model_validate(raw_input)
        except ValidationError as error:
            return _error(f"Invalid input for {name}: {error}")
        return tool.handler(args, ctx)


def _error(message: str, display: dict[str, Any] | None = None) -> ToolOutput:
    return ToolOutput(content=message, display=display or {"error": message}, is_error=True)


class RunSqlInput(BaseModel):
    sql: str = Field(description="One BigQuery Standard SQL SELECT statement, starting from the building blocks.")


def run_sql_tool(runner: SqlRunner, *, preview_rows: int) -> Tool:
    def handler(args: RunSqlInput, ctx: TurnContext) -> ToolOutput:
        try:
            result = runner.run(args.sql)
        except QueryError as error:
            return _error(str(error), display={"sql": args.sql, "error": str(error)})

        result_id = ctx.store(result)
        preview = result.rows[:preview_rows]
        columns = [{"name": c.name, "type": c.type} for c in result.columns]
        sent = {
            "result_id": result_id,
            "columns": columns,
            "total_rows": result.total_rows,
            "rows": preview,
            "note": f"Showing the first {len(preview)} of {result.total_rows} rows.",
        }
        display = {
            "sql": args.sql,
            "result_id": result_id,
            "columns": columns,
            "rows": preview,
            "total_rows": result.total_rows,
        }
        return ToolOutput(content=json.dumps(sent), display=display)

    return Tool(
        name="run_sql",
        description=(
            "Run a read-only SQL query against the dataset and get back a result_id, the columns, "
            "the total row count and a preview of the rows. Errors come back as messages you can "
            "fix and retry."
        ),
        input_model=RunSqlInput,
        handler=handler,
    )
