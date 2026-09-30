"""Centralized, validated configuration for NEXUS (Phase 5).

Not a general configuration framework -- a small set of environment-driven
settings that need validation *before* the app starts serving traffic
(auth mode, database backend, rate limits), read once at startup via
`load_config()`. Everything else in the codebase continues reading its own
env vars locally and independently (tool_policy.py, pricing.py,
run_store.py, evals/store.py, ...) exactly as before; this module exists
because these particular settings interact with each other in a way a
scattered `os.getenv()` per module can't express -- most importantly,
"production without an API token configured" must be a hard startup
error, not a per-request decision silently defaulting to "unauthenticated".

Nothing in this module logs a secret value: `api_token`/`database_url` are
read and carried as plain fields, never written to a log line here or by
any caller that follows the same rule observability.py already enforces.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_ENVIRONMENTS = ("development", "test", "production")

DEFAULT_RATE_LIMIT_REQUESTS = 60
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60.0


class ConfigError(ValueError):
    """Invalid configuration detected at startup. Messages describe which
    setting is wrong -- never the value of a secret setting."""


@dataclass(frozen=True)
class NexusConfig:
    environment: str
    api_token: str | None
    database_url: str | None
    rate_limit_requests: int
    rate_limit_window_seconds: float

    @property
    def auth_enabled(self) -> bool:
        """False only in development mode with no token configured -- see
        auth.py's module docstring for what that mode actually does (it is
        NOT "no principal", it's a fixed, explicit development principal)."""
        return self.api_token is not None

    @property
    def uses_postgres(self) -> bool:
        return self.database_url is not None


def load_config(env: dict | None = None) -> NexusConfig:
    """Read and validate configuration from `env` (defaults to the real
    process environment). Raises `ConfigError` for anything invalid enough
    that starting the app anyway would be misleading -- e.g. a production
    environment with no way to authenticate a caller.
    """
    env = os.environ if env is None else env

    environment = env.get("NEXUS_ENVIRONMENT", "development").strip().lower()
    if environment not in _ENVIRONMENTS:
        raise ConfigError(
            f"NEXUS_ENVIRONMENT must be one of {_ENVIRONMENTS}, got {environment!r}"
        )

    api_token = env.get("NEXUS_API_TOKEN") or None
    database_url = env.get("NEXUS_DATABASE_URL") or None

    if environment == "production" and api_token is None:
        raise ConfigError(
            "NEXUS_ENVIRONMENT=production requires NEXUS_API_TOKEN to be set. NEXUS never "
            "silently treats an unauthenticated production deployment as authenticated -- "
            "set NEXUS_API_TOKEN, or run with NEXUS_ENVIRONMENT=development for local use."
        )

    rate_limit_requests = _positive_int(
        env, "NEXUS_RATE_LIMIT_REQUESTS", DEFAULT_RATE_LIMIT_REQUESTS
    )
    rate_limit_window_seconds = _positive_float(
        env, "NEXUS_RATE_LIMIT_WINDOW_SECONDS", DEFAULT_RATE_LIMIT_WINDOW_SECONDS
    )

    return NexusConfig(
        environment=environment,
        api_token=api_token,
        database_url=database_url,
        rate_limit_requests=rate_limit_requests,
        rate_limit_window_seconds=rate_limit_window_seconds,
    )


def _positive_int(env: dict, key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} must be an integer") from exc
    if value <= 0:
        raise ConfigError(f"{key} must be positive")
    return value


def _positive_float(env: dict, key: str, default: float) -> float:
    raw = env.get(key)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{key} must be a number") from exc
    if value <= 0:
        raise ConfigError(f"{key} must be positive")
    return value
