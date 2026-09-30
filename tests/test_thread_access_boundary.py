"""Thread access boundary (Phase 2, minimal): `thread_id` is an identifier,
not authentication -- these tests verify the ownership bookkeeping that
exists (first-touch principal claims a thread, a different principal is
rejected), NOT a real authentication system. There is no credential check
here and these tests don't pretend otherwise.
"""

import pytest

import access
import main
import runtime as nexus_runtime


class _FakeMessage:
    def __init__(self, content):
        self.content = content


def test_local_cli_principal_can_use_its_own_thread():
    registry = access.ThreadAccessRegistry()
    registry.require_access(access.LOCAL_CLI_PRINCIPAL, "thread-a")
    # Same principal, same thread again: still fine.
    registry.require_access(access.LOCAL_CLI_PRINCIPAL, "thread-a")
    assert registry.owner_of("thread-a") == access.LOCAL_CLI_PRINCIPAL


def test_first_principal_to_touch_a_thread_becomes_its_owner():
    registry = access.ThreadAccessRegistry()
    registry.require_access("principal-a", "thread-x")
    assert registry.owner_of("thread-x") == "principal-a"


def test_unrelated_principal_is_rejected_from_anothers_thread():
    registry = access.ThreadAccessRegistry()
    registry.require_access("principal-a", "thread-x")
    with pytest.raises(access.ThreadAccessDenied):
        registry.require_access("principal-b", "thread-x")


def test_denial_does_not_change_ownership():
    registry = access.ThreadAccessRegistry()
    registry.require_access("principal-a", "thread-x")
    with pytest.raises(access.ThreadAccessDenied):
        registry.require_access("principal-b", "thread-x")
    assert registry.owner_of("thread-x") == "principal-a"


def test_this_is_bookkeeping_not_authentication():
    # No credential of any kind is involved -- a "principal_id" is just a
    # string the caller supplies. Documented explicitly so nobody mistakes
    # this for real auth later.
    registry = access.ThreadAccessRegistry()
    registry.require_access("anyone-can-claim-this-string", "thread-y")
    assert registry.owner_of("thread-y") == "anyone-can-claim-this-string"


@pytest.fixture(autouse=True)
def _fake_llm_calls(monkeypatch):
    monkeypatch.setattr(
        main, "_call_classifier", lambda messages: main.MessageClassifier(message_type="coding")
    )
    monkeypatch.setattr(main, "_call_llm", lambda messages: _FakeMessage("stub reply"))


async def test_runtime_execute_enforces_the_boundary_across_principals(tmp_path):
    db_path = str(tmp_path / "access.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        thread_id = nexus_runtime.new_thread_id()

        first = await session.execute(thread_id, "hello", principal_id="principal-a")
        assert first.success is True

        denied = await session.execute(thread_id, "hi again", principal_id="principal-b")
        assert denied.success is False


async def test_runtime_get_state_enforces_the_boundary_across_principals(tmp_path):
    db_path = str(tmp_path / "access.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        thread_id = nexus_runtime.new_thread_id()
        await session.execute(thread_id, "hello", principal_id="principal-a")

        # Same principal can read its own thread's state.
        snapshot = await session.get_state(thread_id, principal_id="principal-a")
        assert snapshot.values["messages"]

        # A different principal cannot -- this is exactly the "accidental
        # exposure of arbitrary thread_id" a future API must not allow.
        with pytest.raises(access.ThreadAccessDenied):
            await session.get_state(thread_id, principal_id="principal-b")


async def test_owner_of_is_read_only_and_does_not_claim_an_untouched_thread(tmp_path):
    # Phase 6.3: unlike verify_access/require_access, owner_of must never
    # have a first-touch claiming side effect -- it's used to check many
    # already-recorded runs' ownership (GET /v1/runs) without risking an
    # accidental claim on any thread it merely peeks at.
    db_path = str(tmp_path / "access.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        thread_id = nexus_runtime.new_thread_id()

        assert await session.owner_of(thread_id) is None

        first = await session.execute(thread_id, "hello", principal_id="principal-a")
        assert first.success is True
        assert await session.owner_of(thread_id) == "principal-a"

        # A second principal is still rejected -- owner_of didn't secretly
        # claim the thread for anyone when it returned None above.
        denied = await session.execute(thread_id, "hi again", principal_id="principal-b")
        assert denied.success is False
        assert await session.owner_of(thread_id) == "principal-a"


async def test_default_principal_is_the_local_cli_principal(tmp_path):
    # The CLI never passes principal_id explicitly -- confirm the default
    # matches access.LOCAL_CLI_PRINCIPAL so two CLI-driven executions on
    # the same thread never spuriously conflict with each other.
    db_path = str(tmp_path / "access.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        thread_id = nexus_runtime.new_thread_id()
        first = await session.execute(thread_id, "hello")
        second = await session.execute(thread_id, "hello again")
        assert first.success is True
        assert second.success is True
