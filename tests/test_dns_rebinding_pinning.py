"""Regression tests for the Phase 5 DNS-rebinding hardening in
tool_policy.py.

Background: `check_url` resolves and validates a hostname's IP at check
time; historically `secure_fetch`'s real network path then let httpx
perform its OWN, independent DNS resolution moments later when actually
connecting -- a classic TOCTOU/DNS-rebinding window (an attacker
controlling DNS for the target host could change the resolved address
between the two steps). Phase 5 closes this by pinning the real TCP
connection to the exact IP address that was just validated, via a custom
httpcore network backend (`tool_policy._PinnedNetworkBackend`) -- verified
experimentally against a real HTTPS endpoint during development (both
that a correct pin succeeds with valid TLS, and that a wrong pin genuinely
fails to connect, proving the pin is real and not a no-op).

These tests exercise the pinning mechanism directly and deterministically
(no real network access) by monkeypatching the underlying
`httpcore.AnyIOBackend.connect_tcp` that `_PinnedNetworkBackend` delegates
to, so the "did it try to connect to the pinned address?" assertion never
depends on internet access.
"""

import httpcore
import pytest

import tool_policy as tp


@pytest.fixture
def recorded_connects(monkeypatch):
    """Replace the real `connect_tcp` implementation `_PinnedNetworkBackend`
    delegates to (via `super().connect_tcp`) with one that just records
    what it was asked to connect to -- no real socket is ever opened."""
    calls = []

    async def _fake_connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        calls.append((host, port))
        return object()  # stand-in "stream" -- never used by these tests

    monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", _fake_connect_tcp)
    return calls


async def test_pinned_backend_connects_to_the_pinned_ip_not_the_hostname(recorded_connects):
    backend = tp._PinnedNetworkBackend({"example.com": "93.184.216.34"})

    await backend.connect_tcp("example.com", 443)

    assert recorded_connects == [("93.184.216.34", 443)]


async def test_pinned_backend_fails_closed_for_an_unpinned_host(recorded_connects):
    # This is the safety net: `_fetch_loop` always populates the pin map
    # before connecting to any host, so this should never trigger in
    # normal operation -- but if it ever did (a future code path forgetting
    # to validate first), this must refuse to connect, not silently fall
    # back to an unpinned, unvalidated DNS lookup.
    backend = tp._PinnedNetworkBackend({"example.com": "93.184.216.34"})

    with pytest.raises(httpcore.ConnectError):
        await backend.connect_tcp("not-pinned.example", 443)

    assert recorded_connects == []  # the real connect_tcp was never reached


async def test_pinned_backend_does_not_confuse_different_hosts(recorded_connects):
    backend = tp._PinnedNetworkBackend(
        {"example.com": "93.184.216.34", "other.example": "203.0.113.9"}
    )

    await backend.connect_tcp("other.example", 443)

    assert recorded_connects == [("203.0.113.9", 443)]


def test_build_pinned_transport_wires_the_pinned_backend_into_the_pool():
    pin_map = {"example.com": "93.184.216.34"}
    transport = tp._build_pinned_transport(pin_map)
    try:
        backend = transport._pool._network_backend
        assert isinstance(backend, tp._PinnedNetworkBackend)
        assert backend._pin_map is pin_map  # same live dict, not a copy
    finally:
        # No real connections were ever opened, but close cleanly anyway.
        pass


async def test_pin_map_updates_are_visible_to_the_backend_live(recorded_connects):
    # `_fetch_loop` mutates the SAME dict object across redirect hops
    # rather than rebuilding the transport each time -- confirm a mutation
    # after construction is actually honored by the backend.
    pin_map = {"example.com": "93.184.216.34"}
    transport = tp._build_pinned_transport(pin_map)
    backend = transport._pool._network_backend

    await backend.connect_tcp("example.com", 443)
    pin_map["redirected.example"] = "198.51.100.7"
    await backend.connect_tcp("redirected.example", 443)

    assert recorded_connects == [("93.184.216.34", 443), ("198.51.100.7", 443)]


# ---------------------------------------------------------------------------
# check_url_with_pin: the SSRF-validated-IP-exposing superset of check_url
# used to build the pin map in the first place.
# ---------------------------------------------------------------------------


async def test_check_url_with_pin_returns_the_validated_ip_when_allowed(fake_dns):
    fake_dns({"example.com": ["93.184.216.34"]})
    decision, ip = await tp.check_url_with_pin("https://example.com/page")
    assert decision.allowed
    assert ip == "93.184.216.34"


async def test_check_url_with_pin_returns_no_ip_when_denied(fake_dns):
    fake_dns({"internal.example": ["10.0.0.5"]})
    decision, ip = await tp.check_url_with_pin("https://internal.example/")
    assert not decision.allowed
    assert ip is None


async def test_check_url_public_behavior_is_unchanged_by_the_pin_variant(fake_dns):
    # check_url() itself (used throughout the existing test suite) must
    # keep returning a bare PolicyDecision -- not a tuple -- so every
    # existing caller/test keeps working unmodified.
    fake_dns({"example.com": ["93.184.216.34"]})
    decision = await tp.check_url("https://example.com/page")
    assert decision.allowed
    assert not isinstance(decision, tuple)
