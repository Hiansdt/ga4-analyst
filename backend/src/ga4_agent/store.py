"""Conversation storage port and its in-memory adapter."""

import copy
import threading
import uuid
from dataclasses import dataclass, field
from typing import Protocol


class ConversationNotFound(KeyError):
    pass


@dataclass
class Conversation:
    id: str
    messages: list[dict] = field(default_factory=list)  # model history, Messages API shape
    turns: list[dict] = field(default_factory=list)  # per turn: the question and the UI events it produced


class ConversationStore(Protocol):
    def create(self) -> str: ...

    def get(self, conversation_id: str) -> Conversation:
        """A snapshot; changing it does not change the store. Raises ConversationNotFound."""
        ...

    def append_turn(self, conversation_id: str, messages: list[dict], turn: dict) -> None:
        """Atomically add one turn's messages and events."""
        ...


class InMemoryStore:
    # TODO(persistent-conversations): Add a database-backed ConversationStore and select it in bootstrap.py
    # WHY: conversations live in process memory, so Cloud Run is capped at one instance and chats vanish when it scales to zero
    # DONE-WHEN: a conversation created before restarting the server still loads via GET /api/conversations/{id}
    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        conversation_id = uuid.uuid4().hex
        with self._lock:
            self._conversations[conversation_id] = Conversation(conversation_id)
        return conversation_id

    def get(self, conversation_id: str) -> Conversation:
        with self._lock:
            if conversation_id not in self._conversations:
                raise ConversationNotFound(conversation_id)
            return copy.deepcopy(self._conversations[conversation_id])

    def append_turn(self, conversation_id: str, messages: list[dict], turn: dict) -> None:
        with self._lock:
            conversation = self._conversations[conversation_id]
            conversation.messages.extend(copy.deepcopy(messages))
            conversation.turns.append(copy.deepcopy(turn))
