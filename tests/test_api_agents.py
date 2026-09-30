"""API tests for the Phase 6.2 agent registry endpoints
(GET /v1/agents, GET /v1/agents/{agent_id}) and the registry's role as
the authoritative allowlist for direct-agent execution.
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
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "api_agents_test.sqlite"))
    import api

    async with api.app.router.lifespan_context(api.app):
        transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


TEST_TOKEN = "test-agents-token-abc123"


@pytest.fixture
async def authed_client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "api_agents_auth_test.sqlite"))
    monkeypatch.setenv("NEXUS_API_TOKEN", TEST_TOKEN)
    import api

    async with api.app.router.lifespan_context(api.app):
        transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Registry endpoints
# ---------------------------------------------------------------------------


async def test_list_agents_returns_all_four(client):
    resp = await client.get("/v1/agents")
    assert resp.status_code == 200
    body = resp.json()
    assert {a["id"] for a in body} == {"logical", "math", "coding", "counselor"}


async def test_list_agents_includes_typed_metadata(client):
    resp = await client.get("/v1/agents")
    body = resp.json()
    logical = next(a for a in body if a["id"] == "logical")
    assert logical["name"] == "Logical"
    assert logical["status"] == "active"
    assert logical["tools"] == ["fetch"]
    assert "reasoning" in logical["capabilities"]
    assert set(logical["execution_mode"]) == {"auto_route", "direct"}


async def test_get_single_agent(client):
    resp = await client.get("/v1/agents/math")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "math"
    assert body["tools"] == []


async def test_unknown_agent_is_404(client):
    resp = await client.get("/v1/agents/not-a-real-agent")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "AGENT_NOT_FOUND"


async def test_unavailable_agent_still_returns_200_not_404(client, monkeypatch):
    monkeypatch.setattr(main, "logical_react_agent", None)
    resp = await client.get("/v1/agents/logical")
    assert resp.status_code == 200
    assert resp.json()["status"] == "unavailable"


async def test_no_secrets_or_prompts_in_agent_metadata(client):
    resp = await client.get("/v1/agents")
    text = resp.text
    assert "system_prompt" not in text
    assert "You are" not in text  # the literal system prompts all start this way
    assert "api_key" not in text.lower()


# ---------------------------------------------------------------------------
# Authentication / authorization on the registry endpoints
# ---------------------------------------------------------------------------


async def test_list_agents_requires_authentication_when_token_configured(authed_client):
    resp = await authed_client.get("/v1/agents")
    assert resp.status_code == 401


async def test_list_agents_succeeds_with_correct_token(authed_client):
    resp = await authed_client.get("/v1/agents", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 4


async def test_get_agent_requires_authentication_when_token_configured(authed_client):
    resp = await authed_client.get("/v1/agents/logical")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Execution mapping: the registry is the authoritative allowlist
# ---------------------------------------------------------------------------


async def test_registry_agent_id_maps_to_working_direct_execution(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]
    resp = await client.post(
        f"/v1/sessions/{thread_id}/messages", json={"message": "hi", "agent": "math"}
    )
    assert resp.status_code == 200
    assert resp.json()["response"] == "stub reply"


async def test_unknown_agent_id_is_rejected_before_execution(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]
    resp = await client.post(
        f"/v1/sessions/{thread_id}/messages", json={"message": "hi", "agent": "not-a-real-agent"}
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


async def test_unavailable_agent_id_is_rejected_before_execution(client, monkeypatch):
    # This is the key Phase 6.2 guarantee: marking an agent unavailable
    # must actually block execution, not just change what the registry
    # reports.
    monkeypatch.setattr(main, "logical_react_agent", None)
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]
    resp = await client.post(
        f"/v1/sessions/{thread_id}/messages", json={"message": "hi", "agent": "logical"}
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


async def test_unavailable_agent_id_is_rejected_on_the_stream_endpoint_too(client, monkeypatch):
    monkeypatch.setattr(main, "logical_react_agent", None)
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]
    resp = await client.post(
        f"/v1/sessions/{thread_id}/messages/stream", json={"message": "hi", "agent": "logical"}
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Regression: existing Auto Route / Direct Agent behavior is unaffected
# ---------------------------------------------------------------------------


async def test_auto_route_still_works(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]
    resp = await client.post(f"/v1/sessions/{thread_id}/messages", json={"message": "write code"})
    assert resp.status_code == 200
    assert resp.json()["route"] == "coding"


async def test_direct_agent_still_works_and_still_skips_the_classifier(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]
    resp = await client.post(
        f"/v1/sessions/{thread_id}/messages", json={"message": "hi", "agent": "coding"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["route"] is None

    run_resp = await client.get(f"/v1/runs/{body['request_id']}")
    event_types = {e["event_type"] for e in run_resp.json()["events"]}
    assert "classifier_started" not in event_types
