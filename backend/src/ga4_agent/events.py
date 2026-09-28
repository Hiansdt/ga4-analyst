"""Events the agent yields while answering. Transports (SSE, CLI) only consume these."""

from dataclasses import dataclass
from typing import Any


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


Event = TextDelta | ToolStarted | ToolFinished | TurnFailed | TurnCompleted
