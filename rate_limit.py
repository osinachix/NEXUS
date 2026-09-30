"""Bounded, process-local rate limiting for NEXUS's API (Phase 5).

A fixed-window request counter keyed by authenticated `principal_id` (see
auth.py) -- NOT by IP address, since the caller's identity is now known
before this check runs (this dependency is applied after authentication;
see api.py). Process-local and in-memory: a second API process, or a
restart of this one, has its own independent counters. This is explicitly
NOT a distributed/production rate limiter -- see ARCHITECTURE.md's
multi-instance analysis for what a real deployment would need instead
(e.g. a shared Redis- or Postgres-backed counter), deliberately not built
in this phase.

Bounded: tracks at most `max_principals` distinct principals at once
(oldest-touched evicted first), so this cannot grow without bound even
under a flood of distinct principal_ids. Under the current authentication
model (one configured token = one principal, or one fixed development
principal) the number of distinct principals in practice is tiny; the cap
is a structural guarantee, not something expected to be hit.
"""

from __future__ import annotations

import os
import time
from collections import OrderedDict
from dataclasses import dataclass

DEFAULT_MAX_PRINCIPALS = int(os.getenv("NEXUS_RATE_LIMIT_MAX_PRINCIPALS", "10000"))


@dataclass
class _Window:
    window_start: float
    count: int


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: float | None = None


class RateLimiter:
    """One fixed window per principal_id. `check()` both tests and (if
    allowed) consumes one request from the current window -- there is no
    separate "consume" step, so a caller cannot check without counting.
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        max_principals: int = DEFAULT_MAX_PRINCIPALS,
    ):
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if max_principals <= 0:
            raise ValueError("max_principals must be positive")
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._max_principals = max_principals
        self._windows: OrderedDict[str, _Window] = OrderedDict()

    def check(self, principal_id: str, *, now: float | None = None) -> RateLimitResult:
        now = time.monotonic() if now is None else now
        window = self._windows.get(principal_id)

        if window is None or (now - window.window_start) >= self._window_seconds:
            window = _Window(window_start=now, count=0)
            self._windows[principal_id] = window
        self._windows.move_to_end(principal_id)

        while len(self._windows) > self._max_principals:
            self._windows.popitem(last=False)

        if window.count >= self._max_requests:
            retry_after = self._window_seconds - (now - window.window_start)
            return RateLimitResult(allowed=False, retry_after_seconds=max(retry_after, 0.0))

        window.count += 1
        return RateLimitResult(allowed=True)

    def tracked_principal_count(self) -> int:
        """For tests/observability -- confirms the store stays bounded."""
        return len(self._windows)
