"""API tests for the Phase 5 SSE streaming endpoint
(POST /v1/sessions/{thread_id}/messages/stream).

Uses the real FastAPI app over ASGI via httpx's streaming client, exactly
like tests/test_api.py's pattern for the synchronous endpoint. No token is
configured here (development mode), matching tests/test_api.py -- auth
behavior for this endpoint is covered by tests/test_api_auth.py instead.
"""

import asyncio
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
    monkeypatch.setattr(main, "_call_llm", lambda messages: _FakeMessage("streamed reply"))


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "api_sse_test.sqlite"))
    import api

    async with api.app.router.lifespan_context(api.app):
        transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


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


async def _stream(client, thread_id, message):
    async with client.stream(
        "POST", f"/v1/sessions/{thread_id}/messages/stream", json={"message": message}
    ) as resp:
        status_code = resp.status_code
        body = b""
        async for chunk in resp.aiter_bytes():
            body += chunk
    return status_code, _parse_sse(body.decode("utf-8"))


async def test_stream_starts_with_event_stream_content_type(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    async with client.stream(
        "POST", f"/v1/sessions/{thread_id}/messages/stream", json={"message": "hello"}
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        async for _ in resp.aiter_bytes():
            break


async def test_stream_emits_lifecycle_events_ending_with_run_completed(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    status_code, events = await _stream(client, thread_id, "hello")

    assert status_code == 200
    event_types = [e[0] for e in events]
    assert "workflow_started" in event_types
    assert "workflow_completed" in event_types
    assert event_types[-1] == "run_completed"  # always the final event


async def test_stream_events_share_one_request_id_and_thread_id(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    _, events = await _stream(client, thread_id, "hello")

    request_ids = {data["request_id"] for _, data in events if "request_id" in data}
    thread_ids = {data["thread_id"] for _, data in events if "thread_id" in data}
    assert len(request_ids) == 1
    assert thread_ids == {thread_id}


async def test_run_completed_event_carries_the_actual_reply(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    _, events = await _stream(client, thread_id, "hello")

    run_completed = dict(events)["run_completed"]
    assert run_completed["reply"] == "streamed reply"
    assert run_completed["status"] == "completed"
    assert run_completed["success"] is True


async def test_every_event_has_a_timestamp(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    _, events = await _stream(client, thread_id, "hello")

    assert all("timestamp" in data for _, data in events)


async def test_streamed_run_is_recorded_and_retrievable_via_runs_endpoint(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    _, events = await _stream(client, thread_id, "hello")
    request_id = dict(events)["run_completed"]["request_id"]

    run_resp = await client.get(f"/v1/runs/{request_id}")
    assert run_resp.status_code == 200
    body = run_resp.json()
    assert body["request_id"] == request_id
    assert len(body["events"]) > 0
    assert body["status"] == "completed"
    assert body["replayable"] is True


async def test_synchronous_endpoint_is_unaffected_by_streaming(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    resp = await client.post(f"/v1/sessions/{thread_id}/messages", json={"message": "hello"})
    assert resp.status_code == 200
    assert resp.json()["response"] == "streamed reply"


async def test_stream_denies_access_to_a_thread_owned_by_another_principal(client):
    import api

    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]
    api.app.state.runtime._access._owners[thread_id] = "someone-else"

    resp = await client.post(f"/v1/sessions/{thread_id}/messages/stream", json={"message": "hi"})
    assert resp.status_code == 403


async def test_multiple_concurrent_streams_do_not_cross_wires(client):
    thread_a = (await client.post("/v1/sessions")).json()["thread_id"]
    thread_b = (await client.post("/v1/sessions")).json()["thread_id"]

    (_, events_a), (_, events_b) = await asyncio.gather(
        _stream(client, thread_a, "first message"),
        _stream(client, thread_b, "second message"),
    )

    thread_ids_a = {data["thread_id"] for _, data in events_a if "thread_id" in data}
    thread_ids_b = {data["thread_id"] for _, data in events_b if "thread_id" in data}
    assert thread_ids_a == {thread_a}
    assert thread_ids_b == {thread_b}
    assert thread_ids_a != thread_ids_b


async def test_client_disconnect_does_not_leave_a_background_task_running(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    async with client.stream(
        "POST", f"/v1/sessions/{thread_id}/messages/stream", json={"message": "hello"}
    ) as resp:
        async for _ in resp.aiter_bytes():
            break  # simulate the client disconnecting after the first chunk

    # Give any leftover task a chance to be scheduled/cancelled, then confirm
    # the SSE endpoint's own execute() task (named nexus-sse-execute-*, see
    # api.py's _sse_event_source) isn't still running in the background.
    await asyncio.sleep(0.1)
    leftover = [t for t in asyncio.all_tasks() if t.get_name().startswith("nexus-sse-execute-")]
    assert leftover == []


async def test_stream_does_not_leak_secrets(client, monkeypatch):
    planted_secret = "sk-ant-SHOULD-NOT-LEAK-SSE"

    def boom(messages):
        raise RuntimeError(f"failure mentioning {planted_secret}")

    monkeypatch.setattr(main, "_call_llm", boom)

    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    status_code, events = await _stream(client, thread_id, "hello")
    raw = json.dumps(events)
    assert planted_secret not in raw
    assert "Traceback" not in raw
