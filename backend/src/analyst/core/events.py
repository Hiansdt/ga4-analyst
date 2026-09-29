"""Events the agent yields while answering. Transports (SSE, CLI) only consume these."""

from dataclasses import dataclass, field
from typing import Any

from analyst.ports.llm import Usage


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolStarted:
    tool_use_id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class ToolFinished:
    tool_use_id: str
    name: str
    is_error: bool
    display: dict[str, Any]


@dataclass(frozen=True)
class TurnFailed:
    message: str


@dataclass(frozen=True)
class TurnCompleted:
    """Always the last event. `messages` is what this turn adds to the conversation history."""

    messages: list[dict]
    usage: Usage = field(default_factory=Usage)  # summed over every model call of the turn


Event = TextDelta | ToolStarted | ToolFinished | TurnFailed | TurnCompleted
