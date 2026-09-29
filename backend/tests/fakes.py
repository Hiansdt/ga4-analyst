"""Test doubles for the agent's ports."""

from collections.abc import Iterator

from analyst.ports.llm import ModelError, ModelTurn
from analyst.ports.sql import Column, QueryError, QueryParams, QueryResult


class FakeRunner:
    """SqlRunner that returns a fixed result, or raises for SQL containing a marker."""

    def __init__(self, result: QueryResult, fail_on: str = "BROKEN") -> None:
        self.result = result
        self.fail_on = fail_on
        self.queries: list[str] = []
        self.params: list[QueryParams | None] = []

    def run(self, sql: str, params: QueryParams | None = None) -> QueryResult:
        self.queries.append(sql)
        self.params.append(params)
        if self.fail_on in sql:
            raise QueryError("Syntax error: Unexpected identifier BROKEN at [1:1]")
        return self.result


def daily_result(days: int) -> QueryResult:
    rows = [{"day": f"2020-11-{d:02d}", "events": 100 + d} for d in range(1, days + 1)]
    return QueryResult(
        columns=[Column("day", "DATE"), Column("events", "INTEGER")],
        rows=rows,
        total_rows=days,
        bytes_processed=1000,
    )


def text(value: str) -> dict:
    return {"type": "text", "text": value}


def tool_use(tool_use_id: str, name: str, **tool_input) -> dict:
    return {"type": "tool_use", "id": tool_use_id, "name": name, "input": tool_input}


class ScriptedModel:
    """ModelClient that replays scripted turns and records every request."""

    def __init__(self, *turns: ModelTurn | ModelError) -> None:
        self.turns = list(turns)
        self.requests: list[dict] = []

    def stream_turn(
        self, *, system: str, tools: list[dict], messages: list[dict], allow_tools: bool
    ) -> Iterator[str | ModelTurn]:
        self.requests.append({"messages": list(messages), "allow_tools": allow_tools, "tools": tools})
        turn = self.turns.pop(0)
        if isinstance(turn, ModelError):
            raise turn
        for block in turn.content:
            if block["type"] == "text":
                yield block["text"]
        yield turn
