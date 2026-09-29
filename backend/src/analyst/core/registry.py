"""Tool registry: what the model can call, validated before it runs. Adding a tool never touches the loop."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

from analyst.ports.sql import QueryResult


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
            return tool_error(f"Unknown tool {name!r}.")
        try:
            args = tool.input_model.model_validate(raw_input)
        except ValidationError as error:
            return tool_error(f"Invalid input for {name}: {error}")
        return tool.handler(args, ctx)


def tool_error(message: str, display: dict[str, Any] | None = None) -> ToolOutput:
    return ToolOutput(content=message, display=display or {"error": message}, is_error=True)
