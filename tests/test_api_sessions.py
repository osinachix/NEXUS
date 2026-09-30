"""API tests for the Phase 6.4 session-list endpoint (GET /v1/sessions)
and the extended GET /v1/sessions/{thread_id} (now including full message
history). Existing session tests (creation, single-session metadata,
access-boundary basics) live in tests/test_api.py; this file focuses on
what's new: listing, message content, and cross-principal isolation.
"""

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
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "api_sessions_test.sqlite"))
    import api

    async with api.app.router.lifespan_context(api.app):
        transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


TEST_TOKEN = "test-sessions-token-abc123"


@pytest.fixture
async def authed_client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "api_sessions_auth_test.sqlite"))
    monkeypatch.setenv("NEXUS_API_TOKEN", TEST_TOKEN)
    import api

    async with api.app.router.lifespan_context(api.app):
        transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


async def _create_session_with_message(client, message="hello", agent=None):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]
    body = {"message": message}
    if agent is not None:
        body["agent"] = agent
    resp = await client.post(f"/v1/sessions/{thread_id}/messages", json=body)
    assert resp.status_code == 200
    return thread_id


# ---------------------------------------------------------------------------
# Basic listing
# ---------------------------------------------------------------------------


async def test_list_sessions_on_an_empty_store_returns_an_empty_list(client):
    resp = await client.get("/v1/sessions")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


async def test_list_sessions_returns_a_session_just_created(client):
    thread_id = await _create_session_with_message(client, message="write a function")
    resp = await client.get("/v1/sessions")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["thread_id"] == thread_id
    assert item["message_count"] == 2
    assert item["last_route"] == "coding"
    assert item["updated_at"]


async def test_list_sessions_never_includes_full_message_content(client):
    await _create_session_with_message(client, message="a secret message")
    resp = await client.get("/v1/sessions")
    item = resp.json()["items"][0]
    assert item["messages"] is None
    assert "a secret message" not in resp.text
    assert "stub reply" not in resp.text


async def test_list_sessions_orders_most_recently_updated_first(client):
    first = await _create_session_with_message(client, message="first")
    second = await _create_session_with_message(client, message="second")
    resp = await client.get("/v1/sessions")
    ids = [item["thread_id"] for item in resp.json()["items"]]
    assert ids == [second, first]


async def test_list_sessions_respects_limit(client):
    for i in range(3):
        await _create_session_with_message(client, message=f"turn {i}")
    resp = await client.get("/v1/sessions", params={"limit": 2})
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["limit"] == 2


async def test_list_sessions_rejects_a_limit_above_the_maximum(client):
    resp = await client.get("/v1/sessions", params={"limit": 100000})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


async def test_list_sessions_default_limit_is_reasonable(client):
    resp = await client.get("/v1/sessions")
    assert resp.json()["limit"] == 50


# ---------------------------------------------------------------------------
# GET /v1/sessions/{thread_id}: full message history
# ---------------------------------------------------------------------------


async def test_get_session_includes_message_history_oldest_first(client):
    thread_id = await _create_session_with_message(client, message="write a function")
    resp = await client.get(f"/v1/sessions/{thread_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["messages"] == [
        {"role": "human", "content": "write a function"},
        {"role": "ai", "content": "stub reply"},
    ]


async def test_get_session_message_history_never_leaks_internal_fields(client):
    thread_id = await _create_session_with_message(client, message="hi")
    resp = await client.get(f"/v1/sessions/{thread_id}")
    for message in resp.json()["messages"]:
        assert set(message.keys()) == {"role", "content"}


async def test_get_session_for_unknown_thread_is_still_404(client):
    resp = await client.get("/v1/sessions/thread-does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "SESSION_NOT_FOUND"


# ---------------------------------------------------------------------------
# Ownership isolation -- the core Phase 6.4 security requirement
# ---------------------------------------------------------------------------


async def test_list_sessions_never_shows_another_principals_sessions(client):
    thread_id = await _create_session_with_message(client, message="mine")

    # Same technique as tests/test_api.py's / tests/test_api_runs.py's
    # access-boundary tests: reassign the thread's owner directly against
    # the live runtime, since the single-token/dev-mode auth model only
    # ever has one real principal in a test process.
    import api

    runtime = api.app.state.runtime
    runtime._access._owners[thread_id] = "someone-else"

    resp = await client.get("/v1/sessions")
    body = resp.json()
    assert body["items"] == []
    assert thread_id not in resp.text


async def test_direct_session_access_still_rejects_a_non_owner(client):
    thread_id = await _create_session_with_message(client, message="mine")
    import api

    runtime = api.app.state.runtime
    runtime._access._owners[thread_id] = "someone-else"

    resp = await client.get(f"/v1/sessions/{thread_id}")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "THREAD_ACCESS_DENIED"


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


async def test_list_sessions_requires_authentication_when_token_configured(authed_client):
    resp = await authed_client.get("/v1/sessions")
    assert resp.status_code == 401


async def test_list_sessions_succeeds_with_correct_token(authed_client):
    resp = await authed_client.get("/v1/sessions", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /v1/runs?thread_id= (Phase 6.4 Session -> Runs navigation)
# ---------------------------------------------------------------------------


async def test_runs_can_be_filtered_by_thread_id(client):
    thread_a = await _create_session_with_message(client, message="on thread A")
    await _create_session_with_message(client, message="on thread B")

    resp = await client.get("/v1/runs", params={"thread_id": thread_a})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["thread_id"] == thread_a


async def test_runs_filtered_by_another_principals_thread_id_returns_nothing(client):
    thread_id = await _create_session_with_message(client, message="mine")
    import api

    runtime = api.app.state.runtime
    runtime._access._owners[thread_id] = "someone-else"

    resp = await client.get("/v1/runs", params={"thread_id": thread_id})
    assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# No secret/internal leakage
# ---------------------------------------------------------------------------


async def test_list_sessions_never_exposes_secrets(client):
    await _create_session_with_message(client)
    resp = await client.get("/v1/sessions")
    text = resp.text.lower()
    assert "api_key" not in text
    assert "authorization" not in text
    assert "password" not in text
