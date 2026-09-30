"""API-level tests for Phase 6.1's direct-agent execution mode
(MessageRequest.agent), on both the synchronous and SSE endpoints.
"""

import json

import httpx
import pytest

import main


class _FakeMessage:
    def __init__(self, content):
        self.content = content


@pytest.fixture(autouse=True)
def _fake_llm_calls(monkeypatch):
    monkeypatch.setattr(
        main, "_call_classifier", lambda messages: main.MessageClassifier(message_type="coding")
    )
    monkeypatch.setattr(main, "_call_llm", lambda messages: _FakeMessage("stub reply"))


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "api_direct_agent_test.sqlite"))
    import api

    async with api.app.router.lifespan_context(api.app):
        transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


async def test_direct_agent_message_bypasses_classifier(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    resp = await client.post(
        f"/v1/sessions/{thread_id}/messages",
        json={"message": "explain recursion", "agent": "math"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["response"] == "stub reply"
    # No route_selected event ever fired -- classifier never ran.
    assert body["route"] is None

    run_resp = await client.get(f"/v1/runs/{body['request_id']}")
    run_body = run_resp.json()
    event_types = {e["event_type"] for e in run_body["events"]}
    assert "classifier_started" not in event_types
    assert "agent_started" in event_types


async def test_auto_route_message_is_unaffected(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    resp = await client.post(
        f"/v1/sessions/{thread_id}/messages", json={"message": "write a function"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["route"] == "coding"


async def test_invalid_agent_value_is_rejected(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    resp = await client.post(
        f"/v1/sessions/{thread_id}/messages",
        json={"message": "hello", "agent": "not-a-real-agent"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


def _parse_sse(raw_text: str) -> list[tuple[str, dict]]:
    events = []
    for block in raw_text.strip().split("\n\n"):
        if not block.strip():
            continue
        event_type = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event_type = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        if event_type is not None:
            events.append((event_type, data))
    return events


async def test_direct_agent_stream_never_emits_classifier_or_route_events(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    async with client.stream(
        "POST",
        f"/v1/sessions/{thread_id}/messages/stream",
        json={"message": "explain recursion", "agent": "coding"},
    ) as resp:
        assert resp.status_code == 200
        body = b""
        async for chunk in resp.aiter_bytes():
            body += chunk

    events = _parse_sse(body.decode("utf-8"))
    event_types = [e[0] for e in events]
    assert "classifier_started" not in event_types
    assert "route_selected" not in event_types
    assert "workflow_started" in event_types
    assert "agent_started" in event_types
    assert event_types[-1] == "run_completed"
    run_completed = dict(events)["run_completed"]
    assert run_completed["route"] is None
    assert run_completed["reply"] == "stub reply"


async def test_switching_agents_across_turns_on_one_thread(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    r1 = await client.post(
        f"/v1/sessions/{thread_id}/messages", json={"message": "first", "agent": "math"}
    )
    r2 = await client.post(
        f"/v1/sessions/{thread_id}/messages", json={"message": "second", "agent": "coding"}
    )
    r3 = await client.post(
        f"/v1/sessions/{thread_id}/messages", json={"message": "third"}
    )
    assert r1.status_code == r2.status_code == r3.status_code == 200

    session_resp = await client.get(f"/v1/sessions/{thread_id}")
    assert session_resp.json()["message_count"] == 6  # 3 turns x (user + assistant)
