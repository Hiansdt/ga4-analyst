"""HTTP layer: conversation endpoints, with each answer streamed as Server-Sent Events."""

import json
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, StringConstraints

from ga4_agent.agent import Agent
from ga4_agent.events import Event, TextDelta, ToolFinished, ToolStarted, TurnCompleted, TurnFailed
from ga4_agent.store import Conversation, ConversationNotFound, ConversationStore

EVENT_TYPES = {
    TextDelta: "text_delta",
    ToolStarted: "tool_started",
    ToolFinished: "tool_finished",
    TurnFailed: "turn_failed",
    TurnCompleted: "turn_completed",
}


class MessageIn(BaseModel):
    content: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def create_app(agent: Agent, store: ConversationStore, web_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="GA4 Analyst")

    @app.post("/api/conversations", status_code=201)
    def create_conversation() -> dict:
        return {"id": store.create()}

    @app.get("/api/conversations/{conversation_id}")
    def get_conversation(conversation_id: str) -> dict:
        conversation = _get(store, conversation_id)
        return {"id": conversation.id, "turns": conversation.turns}

    @app.post("/api/conversations/{conversation_id}/messages")
    def post_message(conversation_id: str, message: MessageIn) -> StreamingResponse:
        conversation = _get(store, conversation_id)
        return StreamingResponse(
            _answer(agent, store, conversation, message.content),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    if web_dir:
        # Mounted last so /api routes take precedence; html=True serves index.html for "/".
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app


def _get(store: ConversationStore, conversation_id: str) -> Conversation:
    try:
        return store.get(conversation_id)
    except ConversationNotFound:
        raise HTTPException(status_code=404, detail="Conversation not found") from None


def _answer(agent: Agent, store: ConversationStore, conversation: Conversation, question: str) -> Iterator[str]:
    """Stream the turn and save it once complete. Stored events replay through the same UI code."""
    events: list[dict] = []
    for event in agent.run_turn(conversation.messages, question):
        payload = to_payload(event)
        if isinstance(event, TurnCompleted):
            store.append_turn(conversation.id, event.messages, {"question": question, "events": events})
        else:
            events.append(payload)
        yield to_sse(payload)


def to_payload(event: Event) -> dict:
    fields = asdict(event)
    fields.pop("messages", None)  # the model history never leaves the server
    return {"type": EVENT_TYPES[type(event)], **fields}


def to_sse(payload: dict) -> str:
    data = {key: value for key, value in payload.items() if key != "type"}
    return f"event: {payload['type']}\ndata: {json.dumps(data)}\n\n"
