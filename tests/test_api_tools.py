"""Read-only tool registry and ownership-filtered activity API tests."""

import httpx
import pytest

import main
import rate_limit
import run_store


TEST_TOKEN = "test-tools-token-abc123"


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "api_tools_test.sqlite"))
    import api

    async with api.app.router.lifespan_context(api.app):
        transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


@pytest.fixture
async def authed_client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "api_tools_auth_test.sqlite"))
    monkeypatch.setenv("NEXUS_API_TOKEN", TEST_TOKEN)
    import api

    async with api.app.router.lifespan_context(api.app):
        transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


def _record(request_id, thread_id, *, agent="logical", tool_events=None):
    return run_store.RunRecord(
        request_id=request_id,
        thread_id=thread_id,
        status="completed",
        success=True,
        route=agent,
        agent=agent,
        message_type=None,
        reply="sensitive assistant reply must not be projected",
        started_at="2026-01-01T00:00:00+00:00",
        completed_at="2026-01-01T00:00:01+00:00",
        duration_ms=1000,
        tool_events=tool_events or [],
    )


def _event(event_type, timestamp, **kwargs):
    return run_store.ToolEvent(
        tool="fetch",
        event_type=event_type,
        timestamp=timestamp,
        **kwargs,
    )


async def test_tool_registry_reports_actual_fetch_metadata_and_policy(client):
    response = await client.get("/v1/tools")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    fetch = body[0]
    assert fetch["id"] == main.fetch.name == "fetch"
    assert fetch["name"] == "fetch"
    assert fetch["description"] == main.fetch.description
    assert fetch["status"] == "active"
    assert fetch["execution_type"] == "native"
    assert fetch["allowed_agents"] == ["logical"]
    assert any("redirect" in control.lower() for control in fetch["controls"])
    assert any("untrusted" in control.lower() for control in fetch["controls"])


async def test_tool_registry_status_tracks_callable_agent_graph(client, monkeypatch):
    monkeypatch.setattr(main, "logical_react_agent", None)
    response = await client.get("/v1/tools")
    assert response.status_code == 200
    assert response.json()[0]["status"] == "unavailable"


async def test_tool_registry_filters_internal_policy_agents(client, monkeypatch):
    import tool_policy

    monkeypatch.setitem(tool_policy.AGENT_TOOL_POLICY, "internal_worker", frozenset({"fetch"}))
    response = await client.get("/v1/tools")
    assert response.status_code == 200
    assert response.json()[0]["allowed_agents"] == ["logical"]


async def test_tool_endpoints_require_authentication_when_token_is_configured(authed_client):
    assert (await authed_client.get("/v1/tools")).status_code == 401
    assert (await authed_client.get("/v1/tools/activity")).status_code == 401


async def test_tool_endpoints_accept_the_configured_token(authed_client):
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    assert (await authed_client.get("/v1/tools", headers=headers)).status_code == 200
    assert (await authed_client.get("/v1/tools/activity", headers=headers)).status_code == 200


async def test_tool_endpoints_use_existing_rate_limit_dependency(authed_client):
    import api

    api.app.state.rate_limiter = rate_limit.RateLimiter(max_requests=1, window_seconds=3600)
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    assert (await authed_client.get("/v1/tools", headers=headers)).status_code == 200
    limited = await authed_client.get("/v1/tools/activity", headers=headers)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"


async def test_tool_registry_response_contains_only_safe_public_fields(client):
    response = await client.get("/v1/tools")
    assert response.status_code == 200
    text = response.text.lower()
    for forbidden in (
        "authorization", "api_key", "secret", "password", "system_prompt", "dns",
        "ip_address", "raw_arguments", "raw_result", "headers",
    ):
        assert forbidden not in text
    assert set(response.json()[0]) == {
        "id", "name", "description", "status", "execution_type", "allowed_agents", "controls",
    }


async def test_activity_projects_owned_terminal_events_with_parent_agent_and_safe_fields(client):
    import api

    thread_id = "owned-thread"
    events = [
        _event("tool_completed", "2026-01-01T00:00:01+00:00", duration_ms=25, success=True),
        _event("tool_denied", "2026-01-01T00:00:02+00:00", reason="PRIVATE_ADDRESS"),
        _event("tool_failed", "2026-01-01T00:00:03+00:00", duration_ms=40, success=False, error_type="TimeoutError"),
        _event("tool_started", "2026-01-01T00:00:00+00:00"),
    ]
    record = _record("request-owned", thread_id, agent="logical", tool_events=events)
    api.app.state.run_store.record(record)
    api.app.state.runtime._access._owners[thread_id] = "local-api-user"

    response = await client.get("/v1/tools/activity")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert [item["event_type"] for item in body["items"]] == [
        "tool_failed", "tool_denied", "tool_completed",
    ]
    assert {item["agent"] for item in body["items"]} == {"logical"}
    assert {item["request_id"] for item in body["items"]} == {"request-owned"}
    denied = next(item for item in body["items"] if item["event_type"] == "tool_denied")
    failed = next(item for item in body["items"] if item["event_type"] == "tool_failed")
    assert denied["reason"] == "PRIVATE_ADDRESS"
    assert denied["success"] is None
    assert failed["error_type"] == "TimeoutError"
    assert failed["success"] is False
    assert all("thread_id" not in item for item in body["items"])
    assert all("arguments" not in item and "result" not in item for item in body["items"])
    assert "sensitive assistant reply" not in response.text


async def test_activity_excludes_unowned_runs_and_counts_only_owned_events(client):
    import api

    owned = _record("request-owned", "owned-thread", tool_events=[
        _event("tool_completed", "2026-01-01T00:00:01+00:00", success=True),
    ])
    other = _record("request-other", "other-thread", tool_events=[
        _event("tool_denied", "2026-01-01T00:00:02+00:00", reason="TOOL_NOT_AUTHORIZED"),
    ])
    api.app.state.run_store.record(owned)
    api.app.state.run_store.record(other)
    api.app.state.runtime._access._owners["owned-thread"] = "local-api-user"
    api.app.state.runtime._access._owners["other-thread"] = "someone-else"

    response = await client.get("/v1/tools/activity")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["request_id"] for item in response.json()["items"]] == ["request-owned"]
    assert "request-other" not in response.text


async def test_activity_is_bounded_and_has_deterministic_order(client):
    import api

    for index in range(4):
        thread_id = f"thread-{index}"
        record = _record(f"request-{index}", thread_id, tool_events=[
            _event("tool_completed", f"2026-01-01T00:00:0{index}+00:00", success=True),
        ])
        api.app.state.run_store.record(record)
        api.app.state.runtime._access._owners[thread_id] = "local-api-user"

    response = await client.get("/v1/tools/activity", params={"limit": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 4
    assert body["limit"] == 2
    assert [event["request_id"] for event in body["items"]] == ["request-3", "request-2"]


async def test_empty_activity_is_an_honest_empty_result(client):
    response = await client.get("/v1/tools/activity")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50}


async def test_activity_rejects_limits_outside_the_bound(client):
    response = await client.get("/v1/tools/activity", params={"limit": 201})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
