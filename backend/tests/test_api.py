import json

from fakes import FakeRunner, ScriptedModel, daily_result, text, tool_use
from fastapi.testclient import TestClient

from ga4_agent.agent import Agent
from ga4_agent.api import create_app
from ga4_agent.llm import ModelTurn
from ga4_agent.store import InMemoryStore
from ga4_agent.tools import ToolRegistry, run_sql_tool


def answer(value: str) -> ModelTurn:
    return ModelTurn(content=[text(value)], stop_reason="end_turn")


def make_client(*turns: ModelTurn) -> tuple[TestClient, ScriptedModel]:
    model = ScriptedModel(*turns)
    agent = Agent(
        model=model,
        tools=ToolRegistry([run_sql_tool(FakeRunner(daily_result(3)), preview_rows=10)]),
        system_prompt="test",
        max_steps=5,
    )
    return TestClient(create_app(agent, InMemoryStore())), model


def sse_events(body: str) -> list[tuple[str, dict]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def ask(client: TestClient, conversation_id: str, question: str) -> list[tuple[str, dict]]:
    response = client.post(f"/api/conversations/{conversation_id}/messages", json={"content": question})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    return sse_events(response.text)


def test_a_question_streams_typed_events():
    sql_turn = ModelTurn(content=[tool_use("a", "run_sql", sql="SELECT 1")], stop_reason="tool_use")
    client, _ = make_client(sql_turn, answer("There were 3 days."))
    conversation_id = client.post("/api/conversations").json()["id"]

    events = ask(client, conversation_id, "How many days?")

    assert [name for name, _ in events] == [
        "tool_started",
        "tool_finished",
        "text_delta",
        "turn_completed",
    ]
    assert events[1][1]["display"]["total_rows"] == 3
    assert "messages" not in events[-1][1]  # model history stays on the server


def test_follow_up_questions_send_the_previous_turns_to_the_model():
    client, model = make_client(answer("Hello."), answer("Still here."))
    conversation_id = client.post("/api/conversations").json()["id"]

    ask(client, conversation_id, "Hi")
    ask(client, conversation_id, "Again?")

    assert [m["role"] for m in model.requests[1]["messages"]] == ["user", "assistant", "user"]


def test_a_reloaded_conversation_replays_the_same_events():
    client, _ = make_client(answer("Hello."))
    conversation_id = client.post("/api/conversations").json()["id"]
    streamed = ask(client, conversation_id, "Hi")

    stored = client.get(f"/api/conversations/{conversation_id}").json()

    assert stored["turns"] == [
        {"question": "Hi", "events": [{"type": name, **data} for name, data in streamed if name != "turn_completed"]}
    ]


def test_unknown_conversations_are_404():
    client, _ = make_client()

    assert client.get("/api/conversations/missing").status_code == 404
    assert client.post("/api/conversations/missing/messages", json={"content": "Hi"}).status_code == 404


def test_empty_questions_are_rejected():
    client, _ = make_client()
    conversation_id = client.post("/api/conversations").json()["id"]

    response = client.post(f"/api/conversations/{conversation_id}/messages", json={"content": "  "})

    assert response.status_code == 422
