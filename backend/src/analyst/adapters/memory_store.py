"""In-memory conversation store: one process, lost on restart."""

import copy
import threading
import uuid

from analyst.ports.store import Conversation, ConversationNotFound


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
