"""LLM port. Messages use the Anthropic Messages API shape as plain dicts."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol


class ModelError(Exception):
    """The model call failed (network, rate limit, server error). Not something the model can fix."""


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cache_read_input_tokens + other.cache_read_input_tokens,
            self.cache_creation_input_tokens + other.cache_creation_input_tokens,
        )


@dataclass(frozen=True)
class ModelTurn:
    content: list[dict]  # assistant content blocks, JSON-safe
    stop_reason: str
    usage: Usage = field(default_factory=Usage)


class ModelClient(Protocol):
    def stream_turn(
        self, *, system: str, tools: list[dict], messages: list[dict], allow_tools: bool
    ) -> Iterator[str | ModelTurn]:
        """Yield answer text as it streams, then exactly one ModelTurn. Raises ModelError."""
        ...
