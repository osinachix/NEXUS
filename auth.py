"""HTTP-boundary authentication for NEXUS (Phase 5).

Authentication answers "who are you?" -- and happens ONLY at the API
boundary (api.py). `NexusRuntime` and everything below it (LangGraph
nodes, tools, tool_policy.py) continue to know only a plain
`principal_id: str`, exactly as in Phase 2-4: the runtime never sees an
HTTP header, a request object, or this module's `Principal` type. This is
deliberate -- see the Phase 5 spec's "the runtime must not know about HTTP
headers or FastAPI request objects."

    HTTP request
        -> authenticate(authorization_header, configured_token=...)
        -> Principal
        -> NexusRuntime.execute(..., principal_id=principal.principal_id)
        -> authorization/access checks (access.py, unchanged in kind)

Two modes, controlled entirely by whether `config.NexusConfig.api_token`
is set (config.py already refuses to start in production without one):

- Token mode (NEXUS_API_TOKEN set): every request MUST present
  `Authorization: Bearer <token>` matching exactly. Anything else --
  missing header, wrong scheme, malformed value, wrong token -- is an
  `AuthenticationError` (api.py maps this to HTTP 401).
- Development mode (NEXUS_API_TOKEN unset): every request is
  auto-authenticated as one single, fixed, explicit development
  principal -- exactly the "no auth" behavior Phase 3/4 already had. This
  is what keeps the existing test suite, the CLI, and any script written
  against the Phase 3/4 API working unchanged when no token is
  configured. It is not a silent gap: api.py logs once at startup that
  authentication is disabled (see api.py's `lifespan`), and config.py
  refuses to combine this mode with NEXUS_ENVIRONMENT=production.

Authorization (does this principal own this resource?) is a separate
concern handled by access.py, unchanged in kind by this module.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Literal

import access

AuthMethod = Literal["bearer_token", "development_mode"]


@dataclass(frozen=True)
class Principal:
    principal_id: str
    authentication_method: AuthMethod
    metadata: dict[str, str] = field(default_factory=dict)


class AuthenticationError(Exception):
    """Raised for any authentication failure. `detail` is always safe to
    return to an HTTP client as-is -- it never contains the configured
    token, the raw Authorization header value, or any other secret."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


# The fixed principal used for every request while running in development
# mode (no NEXUS_API_TOKEN configured). Deliberately the same principal
# id the API used for every request in Phase 3/4, before auth existed --
# nothing about existing thread ownership changes when a token is added
# later, since new token-authenticated principals are simply different
# ids that would never have owned those threads anyway.
DEVELOPMENT_PRINCIPAL = Principal(
    principal_id=access.LOCAL_API_PRINCIPAL,
    authentication_method="development_mode",
)


def _token_principal_id(token: str) -> str:
    # Never let the configured token appear in (or be recoverable from) a
    # principal_id that might end up in a log line, an observability
    # event, or an error message. A short, stable, one-way hash gives one
    # configured token one consistent principal_id across requests
    # without carrying the secret itself.
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    return f"token-{digest}"


def authenticate(authorization_header: str | None, *, configured_token: str | None) -> Principal:
    """Resolve one HTTP request's `Authorization` header value to a
    `Principal`. Raises `AuthenticationError` for every failure case --
    never returns a partial or guessed identity.

    `configured_token` is `config.NexusConfig.api_token`; pass `None` to
    run in development mode (see module docstring).
    """
    if configured_token is None:
        return DEVELOPMENT_PRINCIPAL

    if not authorization_header:
        raise AuthenticationError("Missing Authorization header.")

    scheme, _, value = authorization_header.partition(" ")
    if scheme != "Bearer" or not value or " " in value:
        raise AuthenticationError("Authorization header must be 'Bearer <token>'.")

    if not hmac.compare_digest(value, configured_token):
        raise AuthenticationError("Invalid bearer token.")

    return Principal(
        principal_id=_token_principal_id(value),
        authentication_method="bearer_token",
    )
