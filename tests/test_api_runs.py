"""API tests for the Phase 6.3 run-list endpoint (GET /v1/runs). The
existing single-run endpoint (GET /v1/runs/{request_id}) is covered by
tests/test_api.py; this file focuses on what's new: listing, ownership
isolation, filtering, limits, and that the detail endpoint's response
shape gained `response`/`agent` without breaking anything.
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
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "api_runs_test.sqlite"))
    import api

    async with api.app.router.lifespan_context(api.app):
        transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


TEST_TOKEN = "test-runs-token-abc123"


@pytest.fixture
async def authed_client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "api_runs_auth_test.sqlite"))
    monkeypatch.setenv("NEXUS_API_TOKEN", TEST_TOKEN)
    import api

    async with api.app.router.lifespan_context(api.app):
        transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


async def _send(client, message="write a function", agent=None):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]
    body = {"message": message}
    if agent is not None:
        body["agent"] = agent
    resp = await client.post(f"/v1/sessions/{thread_id}/messages", json=body)
    assert resp.status_code == 200
    return resp.json()


# ---------------------------------------------------------------------------
# Basic listing
# ---------------------------------------------------------------------------


async def test_list_runs_on_an_empty_store_returns_an_empty_list(client):
    resp = await client.get("/v1/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0


async def test_list_runs_returns_a_run_just_executed(client):
    sent = await _send(client)
    resp = await client.get("/v1/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["request_id"] == sent["request_id"]
    assert body["items"][0]["response"] == "stub reply"
    assert body["items"][0]["agent"] == "coding"


async def test_list_runs_orders_most_recent_first(client):
    first = await _send(client, message="first")
    second = await _send(client, message="second")
    resp = await client.get("/v1/runs")
    ids = [item["request_id"] for item in resp.json()["items"]]
    assert ids == [second["request_id"], first["request_id"]]


async def test_list_runs_includes_direct_agent_runs_with_agent_but_no_route(client):
    sent = await _send(client, message="hi", agent="math")
    resp = await client.get("/v1/runs")
    item = next(i for i in resp.json()["items"] if i["request_id"] == sent["request_id"])
    assert item["route"] is None
    assert item["agent"] == "math"


# ---------------------------------------------------------------------------
# Filtering / limit
# ---------------------------------------------------------------------------


async def test_list_runs_filters_by_status(client, monkeypatch):
    import api

    await _send(client, message="will succeed")

    # A failure outside any node's own try/except (e.g. the checkpointer)
    # is what actually produces status="failed" -- a node-level failure is
    # absorbed into a safe fallback reply and still reports "completed"
    # (see tests/test_api.py's equivalent pair of tests).
    async def _boom(*args, **kwargs):
        raise RuntimeError("simulated checkpointer failure")

    monkeypatch.setattr(api.app.state.runtime._graph, "ainvoke", _boom)
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]
    await client.post(f"/v1/sessions/{thread_id}/messages", json={"message": "will fail"})

    resp = await client.get("/v1/runs", params={"status": "completed"})
    body = resp.json()
    assert body["total"] == 1
    assert all(item["status"] == "completed" for item in body["items"])

    resp_failed = await client.get("/v1/runs", params={"status": "failed"})
    assert resp_failed.json()["total"] == 1


async def test_list_runs_filters_by_agent(client):
    await _send(client, message="hi", agent="math")
    await _send(client, message="hi", agent="coding")

    resp = await client.get("/v1/runs", params={"agent": "math"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["agent"] == "math"


async def test_list_runs_filters_by_route(client):
    await _send(client, message="write code")  # auto-routes to coding
    await _send(client, message="hi", agent="math")  # direct, route stays None

    resp = await client.get("/v1/runs", params={"route": "coding"})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["route"] == "coding"


async def test_list_runs_respects_limit(client):
    for i in range(3):
        await _send(client, message=f"message {i}")

    resp = await client.get("/v1/runs", params={"limit": 2})
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["total"] == 3  # total reflects all matches, not just the page
    assert body["limit"] == 2


async def test_list_runs_rejects_a_limit_above_the_maximum(client):
    resp = await client.get("/v1/runs", params={"limit": 100000})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


async def test_list_runs_rejects_a_non_positive_limit(client):
    resp = await client.get("/v1/runs", params={"limit": 0})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


async def test_list_runs_default_limit_is_reasonable(client):
    resp = await client.get("/v1/runs")
    assert resp.json()["limit"] == 50


async def test_run_summary_list_is_bounded_and_omits_trace_and_reply_data(client):
    first = await _send(client, message="first")
    second = await _send(client, message="second")

    resp = await client.get("/v1/runs/summary", params={"limit": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["limit"] == 1
    assert [item["request_id"] for item in body["items"]] == [second["request_id"]]
    assert body["items"][0]["agent"] == "coding"
    assert body["items"][0]["duration_ms"] >= 0
    assert set(body["items"][0]) == {
        "request_id",
        "status",
        "route",
        "agent",
        "duration_ms",
        "success",
        "created_at",
        "started_at",
        "completed_at",
        "usage",
        "cost_usd",
    }
    assert first["request_id"] not in resp.text
    assert "stub reply" not in resp.text


async def test_run_summary_list_excludes_runs_owned_by_another_principal(client):
    owned = await _send(client, message="mine")
    not_owned = await _send(client, message="not mine")
    import api

    api.app.state.runtime._access._owners[not_owned["thread_id"]] = "someone-else"

    resp = await client.get("/v1/runs/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert [item["request_id"] for item in body["items"]] == [owned["request_id"]]
    assert not_owned["request_id"] not in resp.text


async def test_run_summary_list_uses_existing_authentication(authed_client):
    assert (await authed_client.get("/v1/runs/summary")).status_code == 401
    resp = await authed_client.get(
        "/v1/runs/summary", headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    assert resp.status_code == 200


async def test_run_summary_list_rejects_unbounded_limits(client):
    resp = await client.get("/v1/runs/summary", params={"limit": 51})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


# ---------------------------------------------------------------------------
# Ownership isolation -- the core Phase 6.3 security requirement
# ---------------------------------------------------------------------------


async def test_list_runs_never_shows_another_principals_runs(client):
    sent = await _send(client)

    # Simulate a second principal by reassigning the run's thread to a
    # different owner directly against the live runtime -- the same
    # technique tests/test_api.py's access-boundary test uses, since the
    # single-token/dev-mode auth model only ever has one real principal
    # in a test process (see access.py).
    import api

    runtime = api.app.state.runtime
    runtime._access._owners[sent["thread_id"]] = "someone-else"

    resp = await client.get("/v1/runs")
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []
    # Not leaked anywhere in the raw response body either.
    assert sent["request_id"] not in resp.text


async def test_list_runs_only_counts_owned_runs_towards_total(client):
    import api

    runtime = api.app.state.runtime

    owned = await _send(client, message="mine")
    not_owned = await _send(client, message="not mine")
    runtime._access._owners[not_owned["thread_id"]] = "someone-else"

    resp = await client.get("/v1/runs")
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["request_id"] == owned["request_id"]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


async def test_list_runs_requires_authentication_when_token_configured(authed_client):
    resp = await authed_client.get("/v1/runs")
    assert resp.status_code == 401


async def test_list_runs_succeeds_with_correct_token(authed_client):
    resp = await authed_client.get("/v1/runs", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# No secret/internal leakage
# ---------------------------------------------------------------------------


async def test_list_runs_never_exposes_secrets(client):
    await _send(client)
    resp = await client.get("/v1/runs")
    text = resp.text.lower()
    assert "api_key" not in text
    assert "authorization" not in text
    assert "password" not in text


# ---------------------------------------------------------------------------
# Regression: GET /v1/runs/{request_id} gained fields but is compatible
# ---------------------------------------------------------------------------


async def test_get_single_run_still_works_and_now_includes_response_and_agent(client):
    sent = await _send(client)
    resp = await client.get(f"/v1/runs/{sent['request_id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["response"] == "stub reply"
    assert body["agent"] == "coding"
    assert body["route"] == "coding"


async def test_get_single_run_for_unknown_id_is_still_404(client):
    resp = await client.get("/v1/runs/req-does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "RUN_NOT_FOUND"


async def test_compare_runs_returns_owned_run_data_and_measured_deltas_without_mutation(client):
    import api

    run_a = await _send(client, message="direct math", agent="math")
    run_b = await _send(client, message="automatic code")
    store = api.app.state.run_store
    record_a = store.get(run_a["request_id"])
    record_b = store.get(run_b["request_id"])
    before_a = record_a.model_dump()
    before_b = record_b.model_dump()

    response = await client.get(f"/v1/runs/compare/{run_a['request_id']}/{run_b['request_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["run_a"]["agent"] == "math"
    assert body["run_a"]["route"] is None
    assert body["run_b"]["agent"] == "coding"
    assert body["run_b"]["route"] == "coding"
    assert body["run_a"]["response"] == "stub reply"
    assert body["deltas"]["duration_ms"] is not None
    assert body["deltas"]["input_tokens"] is None
    assert body["deltas"]["output_tokens"] is None
    assert body["deltas"]["total_tokens"] is None
    assert body["deltas"]["cost_usd"] is None
    assert record_a.model_dump() == before_a
    assert record_b.model_dump() == before_b


async def test_compare_runs_hides_missing_and_unowned_runs(client):
    import api

    owned = await _send(client)
    other = await _send(client)
    api.app.state.runtime._access._owners[other["thread_id"]] = "someone-else"

    missing = await client.get(f"/v1/runs/compare/{owned['request_id']}/req-missing")
    unowned = await client.get(f"/v1/runs/compare/{owned['request_id']}/{other['request_id']}")

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "RUN_NOT_FOUND"
    assert unowned.status_code == 404
    assert unowned.json()["error"]["code"] == "RUN_NOT_FOUND"
    assert other["request_id"] not in unowned.text


async def test_compare_runs_rejects_same_run_and_requires_authentication(authed_client):
    same = await authed_client.get(
        "/v1/runs/compare/a/a", headers={"Authorization": f"Bearer {TEST_TOKEN}"}
    )
    unauthenticated = await authed_client.get("/v1/runs/compare/a/b")

    assert same.status_code == 400
    assert same.json()["error"]["code"] == "SAME_RUN"
    assert unauthenticated.status_code == 401


async def test_replay_creates_a_new_owned_run_through_runtime_and_preserves_source(client, monkeypatch):
    import api

    source_input = "replay this private input sentinel"
    source = await _send(client, message=source_input, agent="math")
    source_record = api.app.state.run_store.get(source["request_id"])
    source_before = source_record.model_dump()
    runtime = api.app.state.runtime
    original_execute = runtime.execute
    calls = []

    async def tracked_execute(*args, **kwargs):
        calls.append({"thread_id": args[0], "user_text": args[1], **kwargs})
        return await original_execute(*args, **kwargs)

    monkeypatch.setattr(runtime, "execute", tracked_execute)
    response = await client.post(f"/v1/runs/{source['request_id']}/replay")
    source_response = await client.get(f"/v1/runs/{source['request_id']}")

    assert response.status_code == 200
    assert source_response.status_code == 200
    body = response.json()
    replay_record = api.app.state.run_store.get(body["request_id"])
    assert body["request_id"] != source["request_id"]
    assert body["thread_id"] != source["thread_id"]
    assert body["replay_of"] == source["request_id"]
    assert await runtime.owner_of(body["thread_id"]) == api.auth.DEVELOPMENT_PRINCIPAL.principal_id
    assert body["response"] == "stub reply"
    assert "original_input" not in body
    assert source_input not in response.text
    assert source_input not in source_response.text
    assert len(calls) == 1
    assert calls[0]["user_text"] == source_input
    assert calls[0]["agent"] == "math"
    assert replay_record.requested_agent == "math"
    assert replay_record.replay_of == source["request_id"]
    assert any(event.event_type == "workflow_started" for event in replay_record.events)
    assert replay_record.duration_ms >= 0
    assert source_record.model_dump() == source_before
    assert api.app.state.run_store.get(source["request_id"]) is source_record


async def test_replay_refuses_runs_that_need_prior_thread_state(client):
    created = await client.post("/v1/sessions")
    thread_id = created.json()["thread_id"]
    first = await client.post(f"/v1/sessions/{thread_id}/messages", json={"message": "first"})
    second = await client.post(f"/v1/sessions/{thread_id}/messages", json={"message": "second private input"})
    assert first.status_code == 200

    response = await client.post(f"/v1/runs/{second.json()['request_id']}/replay")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RUN_NOT_REPLAYABLE"
    assert "second private input" not in response.text


async def test_replay_hides_unowned_sources_and_unavailable_sources(client):
    import api

    sent = await _send(client)
    api.app.state.runtime._access._owners[sent["thread_id"]] = "someone-else"

    unowned = await client.post(f"/v1/runs/{sent['request_id']}/replay")
    missing = await client.post("/v1/runs/req-missing/replay")

    assert unowned.status_code == 404
    assert unowned.json()["error"]["code"] == "RUN_NOT_FOUND"
    assert sent["request_id"] not in unowned.text
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "RUN_NOT_FOUND"


async def test_replay_requires_authentication(authed_client):
    unauthenticated = await authed_client.post("/v1/runs/req-source/replay")
    assert unauthenticated.status_code == 401


async def test_replay_refuses_when_bounded_store_cannot_keep_source_and_new_run(client):
    import api

    sent = await _send(client)
    api.app.state.run_store._max_size = 1

    response = await client.post(f"/v1/runs/{sent['request_id']}/replay")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RUN_STORE_CAPACITY"
    assert api.app.state.run_store.get(sent["request_id"]) is not None
