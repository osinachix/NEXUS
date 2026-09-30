"""Deterministic tool/network security policy for NEXUS.

Core principle (do not weaken this): the LLM is not a security boundary.
The model may propose a tool call ("fetch this URL"), but this module is
what independently decides whether that call is actually allowed to
happen - before any network I/O. Every check here is deterministic Python,
not a prompt instruction the model could be talked out of.

Two layers live in this module:

1. Tool authorization (`check_tool_authorized`) - a static, agent -> allowed
   tool-names mapping. Generic; not specific to `fetch`.
2. Network/URL policy (`check_url`) and the fetch implementation itself
   (`secure_fetch`) - specific to the one network-calling tool NEXUS has
   today (`fetch`). `secure_fetch` is NEXUS's own HTTP client, not a wrapper
   around the third-party `mcp-server-fetch` package; see the module-level
   note in `main.py`'s MCP/fetch section for why.

Architectural note on DNS rebinding (Phase 2 identified this gap;
Phase 5 closes it -- see `_build_pinned_transport` below): `check_url`
resolves the hostname and validates the resulting IP address(es) at check
time. Historically, `secure_fetch` then opened its own HTTP connection
moments later, which performed its OWN independent DNS resolution - an
attacker controlling DNS for the target hostname could in principle
change the resolved address between those two steps (a TOCTOU/DNS-
rebinding attack). As of Phase 5, `secure_fetch`'s real (non-test)
network path connects directly to the exact IP address `check_url`
already validated - never re-resolving DNS for the connection itself -
while still verifying the TLS certificate against the original hostname
(SNI + hostname verification unchanged), via httpcore's `network_backend`
extension point. This closes the resolve-then-connect race entirely for
the initial URL and every redirect hop (each of which is re-validated and
re-pinned independently - see `_fetch_loop`). See SECURITY.md for the
verification this was based on and its remaining limitations (e.g. this
does not protect a second, later, independent `fetch` call within the
same tool turn - each call is pinned freshly and correctly, but nothing
here claims to protect a target that legitimately changes IP between two
unrelated calls, which is not the rebinding attack this defends against).
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpcore
import httpx


# ---------------------------------------------------------------------------
# Configuration - all overridable via environment variables, all with a
# secure default. See README "Configuration" / SECURITY.md for the full list.
# ---------------------------------------------------------------------------


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip().lower() for item in value.split(",") if item.strip())


# HTTPS only by default. HTTP is a documented opt-in for local development
# only (e.g. testing against a local HTTP server) - set
# ALLOWED_FETCH_SCHEMES=https,http to enable it. Nothing else is ever valid:
# file://, ftp://, gopher://, data://, javascript://, etc. are always denied
# regardless of this setting, because they are never in the allowed set.
ALLOWED_FETCH_SCHEMES = _split_csv(os.getenv("ALLOWED_FETCH_SCHEMES", "https"))

# Empty by default: no domain restriction (SSRF/scheme/credential checks
# still always apply). Set to a comma-separated exact-host list to restrict
# fetches to specific domains. Matching is EXACT host equality, not suffix
# matching - see `check_domain_allowlist` for why, and README for the
# evil-example.com / example.com.evil.com cases this is chosen to avoid.
ALLOWED_FETCH_DOMAINS = _split_csv(os.getenv("ALLOWED_FETCH_DOMAINS", ""))

MAX_FETCH_RESPONSE_BYTES = int(os.getenv("MAX_FETCH_RESPONSE_BYTES", str(1024 * 1024)))
FETCH_TIMEOUT_SECONDS = float(os.getenv("FETCH_TIMEOUT_SECONDS", "10"))
MAX_REDIRECTS = int(os.getenv("MAX_REDIRECTS", "5"))

_USER_AGENT = "NEXUS-fetch/1.0 (+security-policy-enforced)"


# ---------------------------------------------------------------------------
# Stable, machine-readable denial reason codes (used in observability events
# and safe tool-facing error messages - never a raw exception or traceback).
# ---------------------------------------------------------------------------

class DenyReason:
    SCHEME_NOT_ALLOWED = "SCHEME_NOT_ALLOWED"
    MALFORMED_URL = "MALFORMED_URL"
    CREDENTIALS_IN_URL = "CREDENTIALS_IN_URL"
    HOST_NOT_ALLOWED = "HOST_NOT_ALLOWED"
    PRIVATE_ADDRESS = "PRIVATE_ADDRESS"
    DNS_RESOLUTION_FAILED = "DNS_RESOLUTION_FAILED"
    REDIRECT_NOT_ALLOWED = "REDIRECT_NOT_ALLOWED"
    TOOL_NOT_AUTHORIZED = "TOOL_NOT_AUTHORIZED"
    RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"
    FETCH_TIMEOUT = "FETCH_TIMEOUT"
    FETCH_ERROR = "FETCH_ERROR"


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason_code: str | None = None
    detail: str = ""

    @classmethod
    def allow(cls) -> "PolicyDecision":
        return cls(allowed=True)

    @classmethod
    def deny(cls, reason_code: str, detail: str = "") -> "PolicyDecision":
        return cls(allowed=False, reason_code=reason_code, detail=detail)


class PolicyDeniedError(Exception):
    """Raised by `secure_fetch` when a URL (initial or a redirect target)
    fails policy. Callers (see `main._instrument_tool`) catch this
    specifically to emit a `tool_denied` observability event and return a
    safe, generic denial message - never a raw exception/traceback - as the
    tool's result, so the ReAct loop continues normally instead of crashing.
    """

    def __init__(self, reason_code: str, detail: str = ""):
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(f"{reason_code}: {detail}" if detail else reason_code)


# ---------------------------------------------------------------------------
# Tool authorization: which agent may use which tool at all. Static and
# simple by design (Phase 2 scope explicitly excludes a full RBAC system).
# ---------------------------------------------------------------------------

AGENT_TOOL_POLICY: dict[str, frozenset[str]] = {
    # Only the logical agent has any tool access at all; counselor/math/
    # coding are plain LLM calls with zero tool access (unchanged since
    # Phase 0/1) and are simply absent from this mapping.
    "logical": frozenset({"fetch"}),
}


def check_tool_authorized(agent_name: str, tool_name: str) -> PolicyDecision:
    """Is `agent_name` allowed to call `tool_name` at all? Checked before
    the tool is invoked, regardless of what the model requested - this is
    the layer the model can never talk its way around."""
    allowed = AGENT_TOOL_POLICY.get(agent_name, frozenset())
    if tool_name not in allowed:
        return PolicyDecision.deny(
            DenyReason.TOOL_NOT_AUTHORIZED, f"agent={agent_name!r} tool={tool_name!r}"
        )
    return PolicyDecision.allow()


# ---------------------------------------------------------------------------
# URL / SSRF policy
# ---------------------------------------------------------------------------


def _is_private_or_reserved(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    )


def _check_syntax_and_scheme(url: str) -> tuple[PolicyDecision, str | None]:
    """Cheap, purely-syntactic checks: malformed URL/port, embedded
    credentials, scheme. Returns (decision, hostname); hostname is None
    when the URL was too malformed to extract one."""
    try:
        parts = urlsplit(url)
        _ = parts.port  # accessing .port validates it; raises ValueError if bogus
    except ValueError as exc:
        return PolicyDecision.deny(DenyReason.MALFORMED_URL, str(exc)), None

    if not parts.scheme or not parts.hostname:
        return PolicyDecision.deny(DenyReason.MALFORMED_URL, "missing scheme or host"), None

    if parts.username or parts.password:
        return PolicyDecision.deny(DenyReason.CREDENTIALS_IN_URL), parts.hostname

    if parts.scheme.lower() not in ALLOWED_FETCH_SCHEMES:
        return PolicyDecision.deny(DenyReason.SCHEME_NOT_ALLOWED, f"scheme={parts.scheme!r}"), parts.hostname

    return PolicyDecision.allow(), parts.hostname


def check_domain_allowlist(hostname: str) -> PolicyDecision:
    """Exact-host matching only, deliberately -- not suffix/`.endswith()`
    matching. `evil-example.com` and `example.com.evil.com` must never
    match an allowlist entry of `example.com`; exact-string comparison
    can't have that bug the way a naive suffix check can. Subdomains are
    NOT included automatically: add each one explicitly if needed. An
    empty allowlist means "no domain restriction" (other checks still
    apply) -- see ALLOWED_FETCH_DOMAINS above.
    """
    if not ALLOWED_FETCH_DOMAINS:
        return PolicyDecision.allow()
    host = hostname.lower().rstrip(".")
    if host in ALLOWED_FETCH_DOMAINS:
        return PolicyDecision.allow()
    return PolicyDecision.deny(DenyReason.HOST_NOT_ALLOWED, f"host={hostname!r}")


def _resolve_and_validate(hostname: str) -> tuple[PolicyDecision, str | None]:
    """Resolve `hostname` and reject it if any resolved address is private,
    loopback, link-local, multicast, unspecified, or otherwise reserved
    (this is what catches literal IPs like 127.0.0.1/169.254.169.254 as
    well as hostnames like "localhost" that resolve to them).

    Returns `(decision, ip)` where `ip` is the FIRST validated address --
    the one `_fetch_loop` pins the real connection to (see the module
    docstring's DNS-rebinding note) -- or `None` when denied.
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return PolicyDecision.deny(DenyReason.DNS_RESOLUTION_FAILED, f"host={hostname!r}"), None
    if not infos:
        return PolicyDecision.deny(DenyReason.DNS_RESOLUTION_FAILED, f"host={hostname!r}"), None

    first_ip: str | None = None
    for _family, _type, _proto, _canon, sockaddr in infos:
        raw_ip = sockaddr[0].split("%", 1)[0]  # strip IPv6 zone id if present
        try:
            ip = ipaddress.ip_address(raw_ip)
        except ValueError:
            return PolicyDecision.deny(DenyReason.DNS_RESOLUTION_FAILED, f"host={hostname!r}"), None
        if _is_private_or_reserved(ip):
            return PolicyDecision.deny(DenyReason.PRIVATE_ADDRESS, f"host={hostname!r}"), None
        if first_ip is None:
            first_ip = raw_ip
    return PolicyDecision.allow(), first_ip


def resolve_and_check_ssrf(hostname: str) -> PolicyDecision:
    """Resolve `hostname` and reject it if any resolved address is private
    or otherwise reserved. Public wrapper around `_resolve_and_validate`
    that drops the validated IP -- kept for anything that only needs the
    decision. See the module docstring for the DNS-rebinding note; callers
    that need the validated IP for connection pinning use
    `_resolve_and_validate` directly (see `check_url_with_pin` below).
    """
    return _resolve_and_validate(hostname)[0]


async def check_url(url: str) -> PolicyDecision:
    """The full, composite URL policy: syntax/scheme/credentials, then
    domain allowlist, then SSRF/DNS. Async because DNS resolution runs in a
    thread (it's a blocking call) to avoid stalling the event loop.
    """
    decision, _ip = await check_url_with_pin(url)
    return decision


async def check_url_with_pin(url: str) -> tuple[PolicyDecision, str | None]:
    """Same composite policy as `check_url`, but also returns the
    validated IP address the caller should connect to for THIS url (when
    allowed) -- used by `_fetch_loop` to pin the real network connection to
    exactly the address that was just checked, closing the DNS-rebinding
    TOCTOU window described in the module docstring. `check_url` itself
    (used throughout the existing test suite and by anything that only
    needs the decision) is unchanged and remains the public entrypoint;
    this is the superset used internally by `secure_fetch`.
    """
    decision, hostname = _check_syntax_and_scheme(url)
    if not decision.allowed:
        return decision, None

    domain_decision = check_domain_allowlist(hostname)
    if not domain_decision.allowed:
        return domain_decision, None

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _resolve_and_validate, hostname)


# ---------------------------------------------------------------------------
# The fetch implementation itself. NEXUS's own HTTP client (httpx), not a
# wrapper around a third-party tool's internals, specifically so redirects
# and response size can be enforced under our own control -- see the
# module-level note in main.py's MCP/fetch section.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FetchResult:
    url: str
    status_code: int
    content: str


class _PinnedNetworkBackend(httpcore.AnyIOBackend):
    """A real network backend whose `connect_tcp` always connects to a
    pre-validated, pinned IP address for a given hostname, instead of
    letting the connection perform its own (potentially different) DNS
    resolution at connect time. This is what closes the resolve-then-
    connect TOCTOU window described in the module docstring.

    TLS SNI/certificate hostname verification is unaffected: httpcore
    verifies the certificate against the *original* request hostname
    (`self._origin.host`) regardless of which IP address was actually
    connected to (see `httpcore._async.connection.AsyncHTTPConnection.
    _connect`) - so this only removes the DNS lookup performed at connect
    time, it does not weaken certificate validation. Verified
    experimentally against a real HTTPS endpoint before being added here
    (both that pinning to the correct address succeeds with a valid
    certificate, and that pinning to a wrong address genuinely fails to
    connect rather than silently resolving around it) - see SECURITY.md.

    Fails CLOSED: connecting to a hostname with no pinned entry raises
    rather than silently falling back to a fresh, unpinned DNS lookup.
    `_fetch_loop` always calls `check_url_with_pin` and records the
    validated IP before connecting to any hostname, so this should never
    trigger in normal operation - it exists as a safety net against a
    future code path that forgets to.
    """

    def __init__(self, pin_map: dict[str, str]):
        super().__init__()
        self._pin_map = pin_map

    async def connect_tcp(
        self, host, port, timeout=None, local_address=None, socket_options=None
    ):
        pinned_ip = self._pin_map.get(host)
        if pinned_ip is None:
            raise httpcore.ConnectError(
                f"DNS-rebinding guard: no validated/pinned address for host {host!r} -- "
                "refusing to connect. This indicates a policy check was bypassed, not an "
                "ordinary denial; see tool_policy._PinnedNetworkBackend."
            )
        return await super().connect_tcp(
            pinned_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


def _build_pinned_transport(pin_map: dict[str, str]) -> httpx.AsyncHTTPTransport:
    """Build an httpx transport whose real TCP connections are pinned per
    hostname via `_PinnedNetworkBackend`, reusing httpx's own default TLS
    configuration so certificate verification behaves exactly as httpx's
    normal default transport would. `pin_map` is a live, mutable dict that
    `_fetch_loop` updates as it validates each redirect target in turn, so
    connections to later hosts within the same fetch are pinned too.

    Relies on two private httpx attributes (`transport._pool`,
    `pool._ssl_context`) because httpx's public `AsyncHTTPTransport` API
    has no `network_backend` parameter of its own. If a future httpx
    version removes these attributes, this raises `AttributeError`
    immediately - `secure_fetch`'s caller (`main._instrument_tool`) already
    turns any unexpected exception into a safe `tool_failed` result, so
    this fails closed rather than silently losing the pinning guarantee.
    """
    transport = httpx.AsyncHTTPTransport()
    ssl_context = transport._pool._ssl_context
    transport._pool = httpcore.AsyncConnectionPool(
        ssl_context=ssl_context,
        network_backend=_PinnedNetworkBackend(pin_map),
    )
    return transport


async def _fetch_loop(
    url: str, client: httpx.AsyncClient, pin_map: dict[str, str] | None = None
) -> FetchResult:
    """`pin_map`, when provided (the real/production path - see
    `secure_fetch`), is updated with each redirect target's validated IP
    address before it's followed, so `_PinnedNetworkBackend` above always
    has an entry for whatever host is about to be connected to. `None` in
    tests using an explicit `transport` (e.g. `httpx.MockTransport`), where
    no real TCP connection happens and pinning is a no-op.
    """
    current_url = url
    redirects_followed = 0

    while True:
        try:
            async with client.stream(
                "GET", current_url, headers={"User-Agent": _USER_AGENT}
            ) as response:
                if response.is_redirect:
                    redirects_followed += 1
                    if redirects_followed > MAX_REDIRECTS:
                        raise PolicyDeniedError(
                            DenyReason.REDIRECT_NOT_ALLOWED, "too many redirects"
                        )
                    location = response.headers.get("location")
                    if not location:
                        raise PolicyDeniedError(
                            DenyReason.REDIRECT_NOT_ALLOWED, "redirect missing Location header"
                        )
                    next_url = str(httpx.URL(current_url).join(location))
                    next_decision, next_ip = await check_url_with_pin(next_url)
                    if not next_decision.allowed:
                        raise PolicyDeniedError(
                            DenyReason.REDIRECT_NOT_ALLOWED,
                            f"redirect target denied ({next_decision.reason_code})",
                        )
                    if pin_map is not None and next_ip is not None:
                        pin_map[httpx.URL(next_url).host] = next_ip
                    current_url = next_url
                    continue

                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_FETCH_RESPONSE_BYTES:
                        raise PolicyDeniedError(
                            DenyReason.RESPONSE_TOO_LARGE,
                            f"exceeded {MAX_FETCH_RESPONSE_BYTES} bytes",
                        )

                return FetchResult(
                    url=current_url,
                    status_code=response.status_code,
                    content=bytes(body).decode("utf-8", errors="replace"),
                )
        except httpx.TimeoutException as exc:
            raise PolicyDeniedError(DenyReason.FETCH_TIMEOUT, str(type(exc).__name__)) from exc
        except httpx.HTTPError as exc:
            raise PolicyDeniedError(DenyReason.FETCH_ERROR, str(type(exc).__name__)) from exc


async def secure_fetch(
    url: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> FetchResult:
    """Fetch `url` subject to full policy enforcement: scheme/credentials/
    malformed-URL checks, SSRF/domain checks, a byte cap enforced while
    streaming (not after downloading everything), a request timeout, and
    manual redirect handling where EVERY redirect target is re-validated
    through the same policy before being followed -- never just the
    initial URL. Raises `PolicyDeniedError` if anything is denied.

    The timeout is enforced two ways: httpx's own per-socket timeout (real
    transports only) and an outer `asyncio.wait_for` spanning the whole
    operation (every redirect hop combined), which is transport-agnostic -
    the thing that actually guarantees this can't hang, and what makes the
    timeout observable/testable independent of transport-level details.

    `transport` is a test seam (e.g. `httpx.MockTransport`) so tests can
    exercise real httpx redirect/streaming semantics without real sockets;
    production code never passes it. When `transport` is `None`, this
    builds its own DNS-rebinding-resistant transport (see
    `_build_pinned_transport`) rather than letting `httpx.AsyncClient` pick
    its normal default -- the real connection is pinned to the exact IP
    address `check_url_with_pin` just validated, for the initial URL and
    every redirect hop.
    """
    decision, initial_ip = await check_url_with_pin(url)
    if not decision.allowed:
        raise PolicyDeniedError(decision.reason_code, decision.detail)

    timeout = httpx.Timeout(FETCH_TIMEOUT_SECONDS)

    pin_map: dict[str, str] | None = None
    own_transport = transport
    if transport is None:
        pin_map = {}
        if initial_ip is not None:
            pin_map[httpx.URL(url).host] = initial_ip
        own_transport = _build_pinned_transport(pin_map)

    async with httpx.AsyncClient(
        follow_redirects=False, timeout=timeout, transport=own_transport
    ) as client:
        try:
            return await asyncio.wait_for(
                _fetch_loop(url, client, pin_map), timeout=FETCH_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError as exc:
            raise PolicyDeniedError(DenyReason.FETCH_TIMEOUT, "asyncio.TimeoutError") from exc
