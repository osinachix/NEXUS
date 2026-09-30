"""Confirms the API's application-lifetime runtime architecture (Phase 3,
re-verified for Phase 5): exactly one `NexusRuntime` (and its checkpointer
connection) is created per app lifecycle, reused for every request, and
closed cleanly on shutdown -- never recreated per request.
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


async def test_same_runtime_instance_serves_every_request_in_one_lifespan(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "lifecycle_test.sqlite"))
    import api

    async with api.app.router.lifespan_context(api.app):
        runtime_at_startup = api.app.state.runtime
        transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            for _ in range(3):
                created = await client.post("/v1/sessions")
                thread_id = created.json()["thread_id"]
                await client.post(f"/v1/sessions/{thread_id}/messages", json={"message": "hi"})
                # The exact same NexusRuntime object serves every request --
                # never recreated per call.
                assert api.app.state.runtime is runtime_at_startup


async def test_runtime_and_checkpointer_close_cleanly_on_shutdown(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "lifecycle_shutdown_test.sqlite"))
    import api

    async with api.app.router.lifespan_context(api.app):
        thread_id = await api.app.state.runtime.new_session()
        await api.app.state.runtime.execute(thread_id, "hello")
    # Exiting the lifespan context closes the checkpointer connection (see
    # runtime.create_runtime's `async with AsyncSqliteSaver...`) without
    # raising -- getting here at all is the assertion. A fresh lifespan
    # against the same file afterward proves the connection was released
    # cleanly, not left locked.
    async with api.app.router.lifespan_context(api.app):
        snapshot = await api.app.state.runtime.get_state(thread_id)
        assert snapshot.values["messages"]


async def test_two_independent_lifespans_get_two_independent_runtimes(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "lifecycle_independence_test.sqlite"))
    import api

    seen = []
    for _ in range(2):
        async with api.app.router.lifespan_context(api.app):
            seen.append(api.app.state.runtime)
    assert seen[0] is not seen[1]
