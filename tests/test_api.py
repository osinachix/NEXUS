"""API tests for the Phase 3 FastAPI layer (api.py).

These exercise the real FastAPI app (lifespan included) through its ASGI
interface via httpx -- not a hand-rolled fake app -- so a passing test here
means the actual HTTP contract works, not just that NexusRuntime works in
isolation (already covered by tests/test_runtime_threads.py etc.).

The LLM is mocked (same pattern as the rest of the suite) so no network
access or API key is required; the checkpointer is real SQLite, pointed at
a pytest tmp_path file so tests never touch the real dev database.
"""

import json

import httpx
import pytest

import access
import api
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
    db_path = str(tmp_path / "api_test.sqlite")
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", db_path)
    async with api.app.router.lifespan_context(api.app):
        # raise_app_exceptions=False: match real server behavior, where a
        # registered exception handler's response is what the client sees
        # -- httpx.ASGITransport otherwise re-raises the original exception
        # in-process (a debugging convenience) even though the response
        # was already sent, which would make test_unhandled_runtime_* below
        # fail despite the API behaving correctly.
        transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Health / readiness
# ---------------------------------------------------------------------------


async def test_health_returns_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ok", "service": "nexus-api"}


async def test_ready_reports_ready_once_lifespan_has_started(client):
    resp = await client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checkpointer"] == "ok"


async def test_ready_failure_logs_only_error_type(client, monkeypatch, caplog):
    planted_secret = "private-db-detail-SHOULD-NOT-LEAK"
    caplog.set_level("INFO", logger="nexus.observability")

    async def _boom(*args, **kwargs):
        raise RuntimeError(planted_secret)

    monkeypatch.setattr(api.app.state.runtime, "get_state", _boom)
    resp = await client.get("/ready")

    assert resp.status_code == 503
    assert planted_secret not in resp.text
    assert planted_secret not in caplog.text
    error_events = [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "nexus.observability"
        and '"event_type": "api_error"' in record.getMessage()
    ]
    assert error_events
    assert error_events[-1]["error_type"] == "RuntimeError"
    assert error_events[-1]["path_template"] == "/ready"
    assert "path" not in error_events[-1]


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


async def test_create_session_returns_a_thread_id(client):
    resp = await client.post("/v1/sessions")
    assert resp.status_code == 201
    body = resp.json()
    assert "thread_id" in body
    assert body["thread_id"].startswith("thread-")


async def test_get_session_before_any_message_is_not_found(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    resp = await client.get(f"/v1/sessions/{thread_id}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SESSION_NOT_FOUND"


async def test_get_session_after_a_message_reports_bounded_metadata(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]
    await client.post(f"/v1/sessions/{thread_id}/messages", json={"message": "write a function"})

    resp = await client.get(f"/v1/sessions/{thread_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["thread_id"] == thread_id
    assert body["status"] == "active"
    assert body["message_count"] == 2  # one user turn + one assistant reply
    assert body["last_route"] == "coding"
    assert body["updated_at"]
    # Phase 6.4: full message history is now included, safely (role/content
    # only, oldest first) -- no internal checkpoint/LangChain fields.
    assert body["messages"] == [
        {"role": "human", "content": "write a function"},
        {"role": "ai", "content": "stub reply"},
    ]


async def test_unknown_thread_id_is_not_found(client):
    resp = await client.get("/v1/sessions/thread-does-not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


async def test_message_executes_through_nexus_runtime(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    resp = await client.post(f"/v1/sessions/{thread_id}/messages", json={"message": "write a function"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["response"] == "stub reply"  # proves it went through the mocked graph, not fabricated
    assert body["route"] == "coding"
    assert body["status"] == "completed"


async def test_message_response_contains_request_id_and_thread_id(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    resp = await client.post(f"/v1/sessions/{thread_id}/messages", json={"message": "hello"})
    body = resp.json()
    assert body["thread_id"] == thread_id
    assert body["request_id"].startswith("req-")


async def test_multiple_messages_on_same_thread_preserve_state(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    r1 = await client.post(f"/v1/sessions/{thread_id}/messages", json={"message": "first"})
    r2 = await client.post(f"/v1/sessions/{thread_id}/messages", json={"message": "second"})
    assert r1.json()["request_id"] != r2.json()["request_id"]

    session = await client.get(f"/v1/sessions/{thread_id}")
    assert session.json()["message_count"] == 4  # 2 turns x (user + assistant)


async def test_different_threads_remain_isolated(client):
    thread_a = (await client.post("/v1/sessions")).json()["thread_id"]
    thread_b = (await client.post("/v1/sessions")).json()["thread_id"]

    await client.post(f"/v1/sessions/{thread_a}/messages", json={"message": "thread A turn 1"})
    await client.post(f"/v1/sessions/{thread_a}/messages", json={"message": "thread A turn 2"})
    await client.post(f"/v1/sessions/{thread_b}/messages", json={"message": "thread B turn 1"})

    session_a = (await client.get(f"/v1/sessions/{thread_a}")).json()
    session_b = (await client.get(f"/v1/sessions/{thread_b}")).json()
    assert session_a["message_count"] == 4
    assert session_b["message_count"] == 2


# ---------------------------------------------------------------------------
# Access boundary
# ---------------------------------------------------------------------------


async def test_thread_owned_by_a_different_principal_is_rejected(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    # Manufacture the conflict directly against the same live runtime the
    # API is using (there's only one principal in normal API use today, so
    # this is how the boundary is genuinely exercised -- see access.py).
    runtime = api.app.state.runtime
    runtime._access._owners[thread_id] = "someone-else"

    get_resp = await client.get(f"/v1/sessions/{thread_id}")
    assert get_resp.status_code == 403
    assert get_resp.json()["error"]["code"] == "THREAD_ACCESS_DENIED"

    post_resp = await client.post(f"/v1/sessions/{thread_id}/messages", json={"message": "hi"})
    assert post_resp.status_code == 403
    assert post_resp.json()["error"]["code"] == "THREAD_ACCESS_DENIED"


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


async def test_get_run_returns_recorded_execution_info(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]
    message_resp = await client.post(
        f"/v1/sessions/{thread_id}/messages", json={"message": "write a function"}
    )
    request_id = message_resp.json()["request_id"]

    run_resp = await client.get(f"/v1/runs/{request_id}")
    assert run_resp.status_code == 200
    body = run_resp.json()
    assert body["request_id"] == request_id
    assert body["thread_id"] == thread_id
    assert body["status"] == "completed"
    assert body["route"] == "coding"
    assert body["success"] is True
    assert body["duration_ms"] >= 0


async def test_get_run_for_unknown_request_id_is_not_found(client):
    resp = await client.get("/v1/runs/req-does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RUN_NOT_FOUND"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


async def test_blank_message_is_rejected_with_structured_400(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    resp = await client.post(f"/v1/sessions/{thread_id}/messages", json={"message": "   "})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["code"] == "INVALID_REQUEST"


async def test_missing_message_field_is_rejected_with_structured_400(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]

    resp = await client.post(f"/v1/sessions/{thread_id}/messages", json={})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


async def test_node_level_failure_returns_200_completed_with_safe_fallback_reply(client, monkeypatch):
    # A provider/tool failure inside one specialist node is already caught
    # by Phase 0's node-level fallback (_fallback_reply): the *workflow*
    # still completes with a safe reply, it just isn't the real answer.
    # This is a successful HTTP call -- status="completed" -- not an
    # HTTP-level error. See README "API timeouts".
    def _boom(messages):
        raise RuntimeError("simulated transient provider failure")

    monkeypatch.setattr(main, "_call_llm", _boom)

    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]
    resp = await client.post(f"/v1/sessions/{thread_id}/messages", json={"message": "hello"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["response"] == main.GENERIC_FAILURE_MESSAGE


async def test_workflow_level_failure_returns_200_with_failed_status(client, monkeypatch):
    # A failure outside any node's own try/except (e.g. the checkpointer
    # itself) is what NexusRuntime.execute() reports as success=False --
    # still a safe HTTP 200 with a fallback reply, but status="failed".
    # Same technique as tests/test_observability_events.py's equivalent
    # runtime-level test, exercised here through the real HTTP layer.
    async def _boom(*args, **kwargs):
        raise RuntimeError("simulated checkpointer failure")

    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]
    monkeypatch.setattr(api.app.state.runtime._graph, "ainvoke", _boom)

    resp = await client.post(f"/v1/sessions/{thread_id}/messages", json={"message": "hello"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"


async def test_unhandled_runtime_exception_returns_safe_500(client, monkeypatch, caplog):
    planted_secret = "sk-ant-SHOULD-NOT-LEAK"
    caplog.set_level("INFO", logger="nexus.observability")

    async def _boom(*args, **kwargs):
        raise RuntimeError(f"internal failure containing {planted_secret}")

    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]
    monkeypatch.setattr(api.app.state.runtime, "execute", _boom)

    resp = await client.post(f"/v1/sessions/{thread_id}/messages", json={"message": "hello"})

    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert planted_secret not in resp.text
    assert "RuntimeError" not in resp.text
    assert "Traceback" not in resp.text
    assert planted_secret not in caplog.text
    error_events = [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "nexus.observability"
        and '"event_type": "api_error"' in record.getMessage()
    ]
    assert error_events
    assert error_events[-1]["error_type"] == "RuntimeError"
    assert error_events[-1]["path_template"] == "/v1/sessions/{thread_id}/messages"
    assert "path" not in error_events[-1]


# ---------------------------------------------------------------------------
# OpenAPI
# ---------------------------------------------------------------------------


async def test_docs_are_available(client):
    resp = await client.get("/docs")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


async def test_openapi_json_is_valid_and_includes_expected_endpoints(client):
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["info"]["title"] == "NEXUS API"
    paths = schema["paths"]
    for expected in (
        "/health",
        "/ready",
        "/v1/sessions",
        "/v1/sessions/{thread_id}",
        "/v1/sessions/{thread_id}/messages",
        "/v1/runs/{request_id}",
    ):
        assert expected in paths, f"missing {expected} in OpenAPI schema"
