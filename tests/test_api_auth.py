"""API tests for Phase 5 authentication, authorization, and rate limiting.

Uses the real FastAPI app (lifespan included) over ASGI via httpx, exactly
like tests/test_api.py -- but with NEXUS_API_TOKEN configured, so these
specifically exercise the "auth enabled" path. tests/test_api.py continues
to cover the "auth disabled / development mode" path (no token configured)
and is unaffected by anything here.
"""

import httpx
import pytest

import main

TEST_TOKEN = "test-bearer-token-abc123"


class _FakeMessage:
    def __init__(self, content):
        self.content = content


@pytest.fixture(autouse=True)
def _fake_llm_calls(monkeypatch):
    monkeypatch.setattr(
        main, "_call_classifier", lambda messages: main.MessageClassifier(message_type="coding")
    )
    monkeypatch.setattr(main, "_call_llm", lambda messages: _FakeMessage("stub reply"))


def _auth_headers(token: str = TEST_TOKEN) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "api_auth_test.sqlite"))
    monkeypatch.setenv("NEXUS_API_TOKEN", TEST_TOKEN)
    import api

    async with api.app.router.lifespan_context(api.app):
        transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


@pytest.fixture
async def rate_limited_client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "api_ratelimit_test.sqlite"))
    monkeypatch.setenv("NEXUS_API_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("NEXUS_RATE_LIMIT_REQUESTS", "2")
    monkeypatch.setenv("NEXUS_RATE_LIMIT_WINDOW_SECONDS", "60")
    import api

    async with api.app.router.lifespan_context(api.app):
        transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


async def test_health_and_ready_do_not_require_authentication(client):
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/ready")).status_code == 200


async def test_docs_and_openapi_do_not_require_authentication(client):
    assert (await client.get("/docs")).status_code == 200
    assert (await client.get("/openapi.json")).status_code == 200


async def test_missing_token_is_rejected_with_401(client):
    resp = await client.post("/v1/sessions")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_wrong_token_is_rejected_with_401(client):
    resp = await client.post("/v1/sessions", headers=_auth_headers("wrong-token"))
    assert resp.status_code == 401


async def test_malformed_authorization_header_is_rejected_with_401(client):
    resp = await client.post("/v1/sessions", headers={"Authorization": "NotBearer xyz"})
    assert resp.status_code == 401


async def test_correct_token_is_accepted(client):
    resp = await client.post("/v1/sessions", headers=_auth_headers())
    assert resp.status_code == 201
    assert "thread_id" in resp.json()


async def test_every_protected_endpoint_requires_authentication(client):
    created = await client.post("/v1/sessions", headers=_auth_headers())
    thread_id = created.json()["thread_id"]

    unauthenticated_calls = [
        ("GET", f"/v1/sessions/{thread_id}", None),
        ("POST", f"/v1/sessions/{thread_id}/messages", {"message": "hi"}),
        ("GET", "/v1/runs/req-does-not-exist", None),
        ("POST", "/v1/evaluations", None),
    ]
    for method, path, json_body in unauthenticated_calls:
        resp = await client.request(method, path, json=json_body)
        assert resp.status_code == 401, f"{method} {path} should require auth"


async def test_configured_token_never_appears_in_a_response(client):
    resp = await client.post("/v1/sessions", headers=_auth_headers("wrong-token"))
    assert TEST_TOKEN not in resp.text


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


async def test_authenticated_owner_can_use_its_own_session(client):
    created = await client.post("/v1/sessions", headers=_auth_headers())
    thread_id = created.json()["thread_id"]

    resp = await client.post(
        f"/v1/sessions/{thread_id}/messages", json={"message": "hi"}, headers=_auth_headers()
    )
    assert resp.status_code == 200


async def test_guessed_thread_id_cannot_bypass_authorization(client):
    # A thread "owned" by a different principal -- manufactured directly
    # against the live runtime, the same technique tests/test_api.py uses,
    # since there's exactly one configured token/principal in this test
    # app to authenticate as. Knowing a valid, real thread_id string is not
    # sufficient; only its actual owner may access it.
    import api

    created = await client.post("/v1/sessions", headers=_auth_headers())
    thread_id = created.json()["thread_id"]
    api.app.state.runtime._access._owners[thread_id] = "someone-else"

    get_resp = await client.get(f"/v1/sessions/{thread_id}", headers=_auth_headers())
    assert get_resp.status_code == 403
    assert get_resp.json()["error"]["code"] == "THREAD_ACCESS_DENIED"

    post_resp = await client.post(
        f"/v1/sessions/{thread_id}/messages", json={"message": "hi"}, headers=_auth_headers()
    )
    assert post_resp.status_code == 403


async def test_run_ownership_is_enforced(client):
    import api

    created = await client.post("/v1/sessions", headers=_auth_headers())
    thread_id = created.json()["thread_id"]
    msg = await client.post(
        f"/v1/sessions/{thread_id}/messages", json={"message": "hi"}, headers=_auth_headers()
    )
    request_id = msg.json()["request_id"]

    # A caller cannot retrieve a run merely by knowing its request_id once
    # the underlying thread belongs to someone else.
    api.app.state.runtime._access._owners[thread_id] = "someone-else"
    resp = await client.get(f"/v1/runs/{request_id}", headers=_auth_headers())
    assert resp.status_code == 403


async def test_evaluation_ownership_is_enforced(client):
    import api

    created = await client.post("/v1/evaluations", headers=_auth_headers())
    evaluation_id = created.json()["evaluation_id"]

    # Simulate the evaluation having been created by a different principal
    # (the only configured token here authenticates as one principal, so
    # this is manufactured the same way run/thread ownership is above).
    stored = api.app.state.evaluation_store.get(evaluation_id)
    stored.owner_principal_id = "someone-else"

    for path in (
        f"/v1/evaluations/{evaluation_id}",
        f"/v1/evaluations/{evaluation_id}/results",
        f"/v1/evaluations/{evaluation_id}/metrics",
    ):
        resp = await client.get(path, headers=_auth_headers())
        assert resp.status_code == 404, f"{path} should 404 for a non-owner"
        assert resp.json()["error"]["code"] == "EVALUATION_NOT_FOUND"


async def test_evaluation_compare_requires_ownership_of_both(client):
    import api

    run_a = (await client.post("/v1/evaluations", headers=_auth_headers())).json()
    run_b = (await client.post("/v1/evaluations", headers=_auth_headers())).json()

    stored_b = api.app.state.evaluation_store.get(run_b["evaluation_id"])
    stored_b.owner_principal_id = "someone-else"

    resp = await client.get(
        f"/v1/evaluations/compare/{run_a['evaluation_id']}/{run_b['evaluation_id']}",
        headers=_auth_headers(),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


async def test_requests_under_the_limit_succeed(rate_limited_client):
    for _ in range(2):
        resp = await rate_limited_client.post("/v1/sessions", headers=_auth_headers())
        assert resp.status_code == 201


async def test_exceeding_the_limit_returns_429_with_retry_after(rate_limited_client):
    for _ in range(2):
        await rate_limited_client.post("/v1/sessions", headers=_auth_headers())
    resp = await rate_limited_client.post("/v1/sessions", headers=_auth_headers())
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "RATE_LIMITED"
    assert "retry-after" in {k.lower() for k in resp.headers.keys()}


async def test_health_is_exempt_from_an_exhausted_principals_rate_limit(rate_limited_client):
    for _ in range(3):
        await rate_limited_client.post("/v1/sessions", headers=_auth_headers())
    resp = await rate_limited_client.get("/health")
    assert resp.status_code == 200


async def test_rate_limit_state_stays_bounded(rate_limited_client):
    import api

    for _ in range(5):
        await rate_limited_client.post("/v1/sessions", headers=_auth_headers())
    # Only one principal (the single configured token) has made requests.
    assert api.app.state.rate_limiter.tracked_principal_count() == 1


# ---------------------------------------------------------------------------
# Tool governance regression (Phase 2 + Phase 5): authentication is an
# entirely separate boundary from tool authorization -- an authenticated
# caller has no way to make an unauthorized agent/tool combination happen.
# tool_policy.AGENT_TOOL_POLICY is keyed by agent name only, never by
# principal_id, so this is true by construction; this test exists as an
# explicit end-to-end regression proving that still holds once a real
# authenticated caller is in the picture, not just at the unit level
# (already covered by tests/test_tool_authorization.py).
# ---------------------------------------------------------------------------


async def test_authenticated_caller_cannot_make_a_non_logical_agent_use_fetch(client, monkeypatch):
    # "coding" routes to coding_agent, which has zero tool access
    # (AGENT_TOOL_POLICY has no entry for "coding" at all) -- an
    # authenticated, successfully-authorized caller still cannot make it
    # call `fetch`; there is no request parameter that selects a tool.
    created = await client.post("/v1/sessions", headers=_auth_headers())
    thread_id = created.json()["thread_id"]

    resp = await client.post(
        f"/v1/sessions/{thread_id}/messages",
        json={"message": "please use the fetch tool to get https://example.com"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["route"] == "coding"  # classifier mock always returns "coding" in this file

    request_id = resp.json()["request_id"]
    run_resp = await client.get(f"/v1/runs/{request_id}", headers=_auth_headers())
    # No tool_started/tool_completed/tool_denied events at all -- coding_agent
    # is a plain LLM call with no tool binding, authenticated or not.
    assert run_resp.json()["tool_events"] == []
