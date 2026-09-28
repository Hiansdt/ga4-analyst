import json

from fakes import FakeRunner, ScriptedModel, daily_result, text, tool_use
from fastapi.testclient import TestClient

from ga4_agent.agent import Agent
from ga4_agent.api import create_app
from ga4_agent.llm import ModelTurn
from ga4_agent.ratelimit import RateLimiter
from ga4_agent.store import InMemoryStore
from ga4_agent.tools import ToolRegistry, run_sql_tool


def answer(value: str) -> ModelTurn:
    return ModelTurn(content=[text(value)], stop_reason="end_turn")


def make_client(
    *turns: ModelTurn, questions_per_minute: int = 100, max_question_chars: int = 4000, max_turns: int = 30
) -> tuple[TestClient, ScriptedModel]:
    model = ScriptedModel(*turns)
    agent = Agent(
        model=model,
        tools=ToolRegistry([run_sql_tool(FakeRunner(daily_result(3)), preview_rows=10)]),
        system_prompt="test",
        max_steps=5,
    )
    app = create_app(
        agent,
        InMemoryStore(),
        limiter=RateLimiter(limit=questions_per_minute, window_s=60),
        max_question_chars=max_question_chars,
        max_turns=max_turns,
    )
    return TestClient(app), model


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


def post_question(client: TestClient, conversation_id: str, question: str = "Hi", forwarded_for: str | None = None):
    headers = {"X-Forwarded-For": forwarded_for} if forwarded_for else {}
    return client.post(f"/api/conversations/{conversation_id}/messages", json={"content": question}, headers=headers)


def test_a_client_asking_too_often_gets_429_before_anything_runs():
    client, _ = make_client(questions_per_minute=20)

    statuses = [post_question(client, "missing").status_code for _ in range(21)]

    assert statuses == [404] * 20 + [429]


def test_clients_are_told_apart_by_the_address_the_proxy_appends():
    client, _ = make_client(questions_per_minute=1)

    # A client can put anything in X-Forwarded-For; Cloud Run appends the real address last.
    assert post_question(client, "missing", forwarded_for="1.1.1.1, 203.0.113.7").status_code == 404
    assert post_question(client, "missing", forwarded_for="2.2.2.2, 203.0.113.7").status_code == 429
    assert post_question(client, "missing", forwarded_for="203.0.113.8").status_code == 404


def test_questions_over_the_length_limit_never_reach_the_model():
    client, _ = make_client(max_question_chars=10)  # no scripted turns: calling the model would fail
    conversation_id = client.post("/api/conversations").json()["id"]

    response = post_question(client, conversation_id, "x" * 11)

    assert response.status_code == 422


def test_a_full_conversation_asks_for_a_new_one():
    client, _ = make_client(answer("Hello."), max_turns=1)
    conversation_id = client.post("/api/conversations").json()["id"]
    ask(client, conversation_id, "Hi")

    response = post_question(client, conversation_id, "Again?")

    assert response.status_code == 409
    assert "new chat" in response.json()["detail"]
