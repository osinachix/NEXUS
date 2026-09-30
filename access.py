"""Thread-ownership boundary for NEXUS.

IMPORTANT: this module is authorization bookkeeping ("does this principal
own this thread?"), not authentication ("who is this principal, really?").
As of Phase 5, authentication is a real, separate concern handled at the
API boundary by auth.py, which resolves an HTTP `Authorization` header to
a `principal_id` *before* anything in this module ever runs. This module
still does not verify a credential itself -- it never has and isn't meant
to; see auth.py for that half of the boundary.

Today there are four callers, each passing its own principal_id for every
thread it uses: the CLI (`LOCAL_CLI_PRINCIPAL`), the API's development
mode (`LOCAL_API_PRINCIPAL`, see auth.py's `DEVELOPMENT_PRINCIPAL`), the
Phase 4 evaluation runner (`LOCAL_EVAL_PRINCIPAL`), and -- new in Phase 5
-- any number of distinct `token-<hash>` principals, one per configured
bearer token (see auth.py). `NexusRuntime.execute`/`get_state`/
`new_session` already require a `principal_id` and already check it
against a store, so a caller cannot "accidentally" forget to scope
threads to a principal -- there's no code path that skips the check.

Two implementations of the same first-touch ownership model, chosen by
`runtime.create_runtime` based on whether `NEXUS_DATABASE_URL` is set:

- `ThreadAccessRegistry` -- in-memory, synchronous, process-local. The
  SQLite/development default, unchanged since Phase 2. Does NOT
  coordinate ownership across two processes (e.g. a CLI process and an
  API process sharing one SQLite file) -- only within one running
  process. See ARCHITECTURE.md's multi-instance analysis.
- `PostgresAccessStore` -- async, backed by a small durable table,
  atomic across processes via `INSERT ... ON CONFLICT`. Used only when
  `NEXUS_DATABASE_URL` is configured; this is what makes thread ownership
  itself (not just checkpoint state) safe across multiple API instances
  sharing one Postgres database. See section 14 of the Phase 5 spec --
  deliberately a single two-column table, not a multi-tenant schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

LOCAL_CLI_PRINCIPAL = "local-cli-user"
LOCAL_API_PRINCIPAL = "local-api-user"
LOCAL_EVAL_PRINCIPAL = "local-eval-user"


class ThreadAccessDenied(Exception):
    def __init__(self, principal_id: str, thread_id: str):
        self.principal_id = principal_id
        self.thread_id = thread_id
        super().__init__(f"principal {principal_id!r} may not access thread {thread_id!r}")


@runtime_checkable
class AccessStore(Protocol):
    """What `NexusRuntime` needs from either ownership backend. Methods
    may be sync or async on the concrete implementation -- see
    `runtime.NexusRuntime.verify_access`, which adapts to either so this
    protocol itself doesn't have to force one calling convention."""

    def require_access(self, principal_id: str, thread_id: str):  # -> None | Awaitable[None]
        ...

    def owner_of(self, thread_id: str):  # -> str | None | Awaitable[str | None]
        ...


@dataclass
class ThreadAccessRegistry:
    """First-touch thread ownership, enforced for the lifetime of one
    registry instance (in-memory only -- not persisted across restarts;
    a real implementation would back this with the same durable store as
    thread state, once a real principal/credential concept exists).

    The first principal to use a given `thread_id` becomes its owner; any
    other principal is denied. This is ownership bookkeeping, not
    authentication -- it stops one principal from *accidentally or
    carelessly* reusing another's thread_id within a process's lifetime,
    it does not verify identity.
    """

    _owners: dict[str, str] = field(default_factory=dict)

    def require_access(self, principal_id: str, thread_id: str) -> None:
        owner = self._owners.get(thread_id)
        if owner is None:
            self._owners[thread_id] = principal_id
            return
        if owner != principal_id:
            raise ThreadAccessDenied(principal_id, thread_id)

    def owner_of(self, thread_id: str) -> str | None:
        return self._owners.get(thread_id)


class PostgresAccessStore:
    """Durable, cross-process thread ownership backed by a small Postgres
    table. Same first-touch semantics as `ThreadAccessRegistry`, but the
    claim itself is atomic across processes via `INSERT ... ON CONFLICT
    DO NOTHING` -- two API instances racing to touch the same brand-new
    thread_id can't both believe they won.

    Requires `psycopg[binary,pool]` (an optional dependency -- see
    pyproject.toml's `postgres` extra); only imported here, lazily, so
    installing/running NEXUS without Postgres never needs this package.

    Constructed with an already-open `psycopg_pool.AsyncConnectionPool`
    (see `runtime.create_runtime`, which owns that pool's lifecycle) --
    this class only ever borrows connections from it, never opens or
    closes the pool itself.
    """

    _TABLE = "nexus_thread_owners"

    def __init__(self, pool) -> None:
        self._pool = pool

    async def setup(self) -> None:
        """Create the ownership table if it doesn't exist yet. Called once
        by `runtime.create_runtime` at startup, mirroring the checkpointer's
        own `.setup()` call -- see runtime.py."""
        async with self._pool.connection() as conn:
            await conn.execute(
                f"CREATE TABLE IF NOT EXISTS {self._TABLE} ("
                f"    thread_id TEXT PRIMARY KEY,"
                f"    principal_id TEXT NOT NULL,"
                f"    created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                f")"
            )

    async def require_access(self, principal_id: str, thread_id: str) -> None:
        async with self._pool.connection() as conn:
            claim_cursor = await conn.execute(
                f"INSERT INTO {self._TABLE} (thread_id, principal_id) VALUES (%s, %s) "
                f"ON CONFLICT (thread_id) DO NOTHING RETURNING principal_id",
                (thread_id, principal_id),
            )
            claimed = await claim_cursor.fetchone()
            if claimed is not None:
                return  # We just atomically claimed this thread_id.

            existing_cursor = await conn.execute(
                f"SELECT principal_id FROM {self._TABLE} WHERE thread_id = %s", (thread_id,)
            )
            existing = await existing_cursor.fetchone()

        owner = existing[0] if existing else None
        if owner != principal_id:
            raise ThreadAccessDenied(principal_id, thread_id)

    async def owner_of(self, thread_id: str) -> str | None:
        async with self._pool.connection() as conn:
            cursor = await conn.execute(
                f"SELECT principal_id FROM {self._TABLE} WHERE thread_id = %s", (thread_id,)
            )
            row = await cursor.fetchone()
        return row[0] if row else None
