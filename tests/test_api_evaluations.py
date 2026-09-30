"""API tests for the Phase 4 evaluation endpoints. Same pattern as
tests/test_api.py: the real FastAPI app (lifespan included) over ASGI, LLM
mocked, no network/API key required.
"""

import httpx
import pytest

import main
import rate_limit


class _FakeMessage:
    def __init__(self, content):
        self.content = content


@pytest.fixture(autouse=True)
def _fake_llm_calls(monkeypatch):
    def fake_classify(messages):
        text = messages[-1]["content"]
        if "reverse" in text:
            return main.MessageClassifier(message_type="coding")
        if "overwhelmed" in text:
            return main.MessageClassifier(message_type="emotional")
        if "fetch" in text.lower():
            return main.MessageClassifier(message_type="logical")
        return main.MessageClassifier(message_type="math")

    async def fake_logical_agent(user_text, config=None):
        return {"messages": [_FakeMessage("here is what I found")]}

    monkeypatch.setattr(main, "_call_classifier", fake_classify)
    monkeypatch.setattr(main, "_call_llm", lambda messages: _FakeMessage("391 is the answer, def f(): pass"))
    # Without this, the baseline dataset's logical/"fetch" case would drive
    # the REAL logical_react_agent (built for real by api.py's lifespan)
    # and make a genuine network call to the LLM provider -- exactly what
    # the deterministic test suite must never require (see evals/run.py's
    # docstring on the live-vs-deterministic split).
    monkeypatch.setattr(main, "_call_logical_agent", fake_logical_agent)


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "api_eval_test.sqlite"))
    import api  # imported after env is set, matching tests/test_api.py's fixture

    async with api.app.router.lifespan_context(api.app):
        transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


TEST_TOKEN = "test-evaluations-token-abc123"
OTHER_TEST_TOKEN = "test-evaluations-token-def456"


@pytest.fixture
async def authed_client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "api_eval_auth_test.sqlite"))
    monkeypatch.setenv("NEXUS_API_TOKEN", TEST_TOKEN)
    import api

    async with api.app.router.lifespan_context(api.app):
        transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


async def test_create_evaluation_runs_the_baseline_dataset(client):
    resp = await client.post("/v1/evaluations")
    assert resp.status_code == 201
    body = resp.json()
    assert body["dataset_name"] == "baseline"
    assert body["total_cases"] >= 4
    assert "evaluation_id" in body


async def test_get_evaluation_summary(client):
    created = (await client.post("/v1/evaluations")).json()
    resp = await client.get(f"/v1/evaluations/{created['evaluation_id']}")
    assert resp.status_code == 200
    assert resp.json()["evaluation_id"] == created["evaluation_id"]


async def test_get_evaluation_results(client):
    created = (await client.post("/v1/evaluations")).json()
    resp = await client.get(f"/v1/evaluations/{created['evaluation_id']}/results")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == created["total_cases"]
    assert all("case_id" in r and "passed" in r and "run" in r for r in results)


async def test_get_evaluation_metrics(client):
    created = (await client.post("/v1/evaluations")).json()
    resp = await client.get(f"/v1/evaluations/{created['evaluation_id']}/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == created["total_cases"]
    assert "latency_p95_ms" in body


async def test_list_evaluations_returns_lightweight_summaries_newest_first(client):
    first = (await client.post("/v1/evaluations")).json()
    second = (await client.post("/v1/evaluations")).json()

    response = await client.get("/v1/evaluations")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 50
    assert [item["evaluation_id"] for item in body["items"]] == [
        second["evaluation_id"],
        first["evaluation_id"],
    ]
    assert all("results" not in item and "owner_principal_id" not in item for item in body["items"])


async def test_list_evaluations_empty_store(client):
    response = await client.get("/v1/evaluations")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50}


async def test_list_evaluations_filters_to_owned_only(client):
    import api

    owned = (await client.post("/v1/evaluations")).json()
    other = (await client.post("/v1/evaluations")).json()
    api.app.state.evaluation_store.get(other["evaluation_id"]).owner_principal_id = "another-principal"

    response = await client.get("/v1/evaluations")
    body = response.json()
    assert body["total"] == 1
    assert [item["evaluation_id"] for item in body["items"]] == [owned["evaluation_id"]]
    assert other["evaluation_id"] not in response.text


async def test_evaluations_are_isolated_between_distinct_authenticated_principals(authed_client):
    from dataclasses import replace

    import api

    original_config = api.app.state.config
    owner_headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    other_headers = {"Authorization": f"Bearer {OTHER_TEST_TOKEN}"}

    owner_evaluation = await authed_client.post("/v1/evaluations", headers=owner_headers)
    assert owner_evaluation.status_code == 201
    owner_id = owner_evaluation.json()["evaluation_id"]

    owner_list = await authed_client.get("/v1/evaluations", headers=owner_headers)
    assert owner_list.status_code == 200
    assert [item["evaluation_id"] for item in owner_list.json()["items"]] == [owner_id]

    # This API intentionally supports one configured bearer token at a time.
    # Switch it between sequential requests so both credentials pass the real
    # authentication dependency and resolve to different token-derived
    # principals in this test app.
    api.app.state.config = replace(original_config, api_token=OTHER_TEST_TOKEN)
    try:
        other_evaluation = await authed_client.post("/v1/evaluations", headers=other_headers)
        assert other_evaluation.status_code == 201
        other_id = other_evaluation.json()["evaluation_id"]

        other_list = await authed_client.get("/v1/evaluations", headers=other_headers)
        assert other_list.status_code == 200
        assert [item["evaluation_id"] for item in other_list.json()["items"]] == [other_id]
        assert owner_id not in other_list.text

        owner_paths = [
            f"/v1/evaluations/{owner_id}",
            f"/v1/evaluations/{owner_id}/results",
            f"/v1/evaluations/{owner_id}/metrics",
            f"/v1/evaluations/compare/{owner_id}/{other_id}",
        ]
        safe_message = (
            "No evaluation with this evaluation_id is available (it may predate this API "
            "process or have been evicted from the bounded in-process store)."
        )
        for path in owner_paths:
            response = await authed_client.get(path, headers=other_headers)
            assert response.status_code == 404
            assert response.json() == {
                "error": {"code": "EVALUATION_NOT_FOUND", "message": safe_message}
            }
    finally:
        api.app.state.config = original_config


async def test_list_evaluations_respects_limit_and_rejects_out_of_range(client):
    for _ in range(2):
        await client.post("/v1/evaluations")
    response = await client.get("/v1/evaluations", params={"limit": 1})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["total"] == 2
    assert response.json()["limit"] == 1
    assert (await client.get("/v1/evaluations", params={"limit": 0})).status_code == 400
    assert (await client.get("/v1/evaluations", params={"limit": 201})).status_code == 400


async def test_evicted_evaluation_is_not_listed_or_retrievable(client):
    import api
    import evals.store

    api.app.state.evaluation_store = evals.store.EvaluationStore(max_size=1)
    first = (await client.post("/v1/evaluations")).json()
    second = (await client.post("/v1/evaluations")).json()
    listed = await client.get("/v1/evaluations")
    assert [item["evaluation_id"] for item in listed.json()["items"]] == [second["evaluation_id"]]
    assert (await client.get(f"/v1/evaluations/{first['evaluation_id']}")).status_code == 404


async def test_list_evaluations_requires_auth_when_token_configured(authed_client):
    assert (await authed_client.get("/v1/evaluations")).status_code == 401
    response = await authed_client.get("/v1/evaluations", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
    assert response.status_code == 200


async def test_list_evaluations_is_rate_limited(authed_client):
    import api

    api.app.state.rate_limiter = rate_limit.RateLimiter(max_requests=1, window_seconds=60)
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    assert (await authed_client.get("/v1/evaluations", headers=headers)).status_code == 200
    limited = await authed_client.get("/v1/evaluations", headers=headers)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"


async def test_unknown_evaluation_id_is_not_found(client):
    resp = await client.get("/v1/evaluations/eval-does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "EVALUATION_NOT_FOUND"

    resp2 = await client.get("/v1/evaluations/eval-does-not-exist/results")
    assert resp2.status_code == 404

    resp3 = await client.get("/v1/evaluations/eval-does-not-exist/metrics")
    assert resp3.status_code == 404


async def test_compare_two_evaluations(client):
    run_a = (await client.post("/v1/evaluations")).json()
    run_b = (await client.post("/v1/evaluations")).json()

    resp = await client.get(f"/v1/evaluations/compare/{run_a['evaluation_id']}/{run_b['evaluation_id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["evaluation_id_a"] == run_a["evaluation_id"]
    assert body["evaluation_id_b"] == run_b["evaluation_id"]
    assert "execution_success_rate_delta" in body


async def test_compare_with_missing_evaluation_is_not_found(client):
    run_a = (await client.post("/v1/evaluations")).json()
    resp = await client.get(f"/v1/evaluations/compare/{run_a['evaluation_id']}/eval-does-not-exist")
    assert resp.status_code == 404


async def test_run_created_during_evaluation_is_retrievable_via_runs_endpoint(client):
    created = (await client.post("/v1/evaluations")).json()
    results = (await client.get(f"/v1/evaluations/{created['evaluation_id']}/results")).json()
    request_id = results[0]["request_id"]

    run_resp = await client.get(f"/v1/runs/{request_id}")
    assert run_resp.status_code == 200
    body = run_resp.json()
    assert body["request_id"] == request_id
    # Phase 4 enrichment present and safe.
    assert "events" in body and isinstance(body["events"], list)
    assert "tool_events" in body


# --- security -----------------------------------------------------------


async def test_evaluation_endpoints_never_expose_secrets(client, monkeypatch):
    planted_secret = "sk-ant-SHOULD-NOT-LEAK-EVAL"

    def boom(messages):
        raise RuntimeError(f"failure mentioning {planted_secret}")

    monkeypatch.setattr(main, "_call_llm", boom)

    resp = await client.post("/v1/evaluations")
    assert resp.status_code in (201, 500)
    assert planted_secret not in resp.text

    if resp.status_code == 201:
        evaluation_id = resp.json()["evaluation_id"]
        results_resp = await client.get(f"/v1/evaluations/{evaluation_id}/results")
        assert planted_secret not in results_resp.text
        assert "Traceback" not in results_resp.text
