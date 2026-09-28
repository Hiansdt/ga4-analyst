"""LLM port. Messages use the Anthropic Messages API shape as plain dicts."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol


class ModelError(Exception):
    """The model call failed (network, rate limit, server error). Not something the model can fix."""


@dataclass(frozen=True)
class ModelTurn:
    content: list[dict]  # assistant content blocks, JSON-safe
    stop_reason: str


class ModelClient(Protocol):
    def stream_turn(
        self, *, system: str, tools: list[dict], messages: list[dict], allow_tools: bool
    ) -> Iterator[str | ModelTurn]:
        """Yield answer text as it streams, then exactly one ModelTurn. Raises ModelError."""
        ...
