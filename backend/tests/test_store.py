import pytest

from analyst.adapters.memory_store import InMemoryStore
from analyst.ports.store import ConversationNotFound


def test_new_conversations_start_empty():
    store = InMemoryStore()

    conversation = store.get(store.create("shop"))

    assert conversation.dataset == "shop"
    assert conversation.messages == []
    assert conversation.turns == []


def test_appending_a_turn_extends_history_and_turns():
    store = InMemoryStore()
    conversation_id = store.create("shop")
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": [{"type": "text", "text": "Hello"}]},
    ]

    store.append_turn(conversation_id, messages, {"question": "Hi", "events": []})

    conversation = store.get(conversation_id)
    assert conversation.messages == messages
    assert conversation.turns == [{"question": "Hi", "events": []}]


def test_get_returns_a_snapshot_the_caller_cannot_mutate():
    store = InMemoryStore()
    conversation_id = store.create("shop")

    store.get(conversation_id).messages.append({"role": "user", "content": "sneaky"})

    assert store.get(conversation_id).messages == []


def test_unknown_conversations_raise():
    with pytest.raises(ConversationNotFound):
        InMemoryStore().get("missing")
