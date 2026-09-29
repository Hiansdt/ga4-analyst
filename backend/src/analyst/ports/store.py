"""Conversation storage port. Adapters implement `ConversationStore`."""

from dataclasses import dataclass, field
from typing import Protocol


class ConversationNotFound(KeyError):
    pass


@dataclass
class Conversation:
    id: str
    dataset: str  # the dataset this chat is about; it never changes
    messages: list[dict] = field(default_factory=list)  # model history, Messages API shape
    turns: list[dict] = field(default_factory=list)  # per turn: the question and the UI events it produced


class ConversationStore(Protocol):
    def create(self, dataset: str) -> str: ...

    def get(self, conversation_id: str) -> Conversation:
        """A snapshot; changing it does not change the store. Raises ConversationNotFound."""
        ...

    def append_turn(self, conversation_id: str, messages: list[dict], turn: dict) -> None:
        """Atomically add one turn's messages and events."""
        ...
