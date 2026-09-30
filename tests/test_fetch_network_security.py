"""Network-level fetch security: redirect revalidation, response size
limits enforced while streaming, and request timeouts.

Exercised against real httpx redirect/streaming/timeout-wrapper semantics
via `httpx.MockTransport` (see `tool_policy.secure_fetch`'s `transport`
parameter) -- no real sockets or internet access are used. SSRF/domain
checks still run for real (using `fake_dns` for determinism), so these
tests prove the *whole* pipeline, not just the transport mechanics.
"""

import asyncio

import httpx
import pytest

import tool_policy as tp


@pytest.fixture(autouse=True)
def _policy_defaults(monkeypatch):
    monkeypatch.setattr(tp, "ALLOWED_FETCH_SCHEMES", ("https",))
    monkeypatch.setattr(tp, "ALLOWED_FETCH_DOMAINS", ())
    monkeypatch.setattr(tp, "MAX_FETCH_RESPONSE_BYTES", 1024 * 1024)
    monkeypatch.setattr(tp, "MAX_REDIRECTS", 5)
    monkeypatch.setattr(tp, "FETCH_TIMEOUT_SECONDS", 5.0)


@pytest.fixture(autouse=True)
def _dns(fake_dns):
    fake_dns({
        "example.com": ["93.184.216.34"],
        "internal.example": ["10.0.0.5"],
        "other.example": ["93.184.216.40"],
    })


def _transport(handler):
    return httpx.MockTransport(handler)


async def test_successful_fetch_returns_content():
    def handler(request):
        return httpx.Response(200, text="hello world")

    result = await tp.secure_fetch("https://example.com/page", transport=_transport(handler))
    assert result.content == "hello world"
    assert result.status_code == 200


async def test_allowed_redirect_is_followed():
    def handler(request):
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "/final"})
        return httpx.Response(200, text="final page")

    result = await tp.secure_fetch("https://example.com/start", transport=_transport(handler))
    assert result.content == "final page"
    assert result.url == "https://example.com/final"


async def test_redirect_to_private_address_is_blocked():
    def handler(request):
        if request.url.host == "example.com":
            return httpx.Response(302, headers={"Location": "https://internal.example/secret"})
        return httpx.Response(200, text="should never be reached")  # pragma: no cover

    with pytest.raises(tp.PolicyDeniedError) as exc_info:
        await tp.secure_fetch("https://example.com/start", transport=_transport(handler))
    assert exc_info.value.reason_code == tp.DenyReason.REDIRECT_NOT_ALLOWED


async def test_redirect_to_disallowed_domain_is_blocked(monkeypatch):
    monkeypatch.setattr(tp, "ALLOWED_FETCH_DOMAINS", ("example.com",))

    def handler(request):
        if request.url.host == "example.com":
            return httpx.Response(302, headers={"Location": "https://other.example/"})
        return httpx.Response(200, text="should never be reached")  # pragma: no cover

    with pytest.raises(tp.PolicyDeniedError) as exc_info:
        await tp.secure_fetch("https://example.com/start", transport=_transport(handler))
    assert exc_info.value.reason_code == tp.DenyReason.REDIRECT_NOT_ALLOWED


async def test_excessive_redirects_are_blocked(monkeypatch):
    monkeypatch.setattr(tp, "MAX_REDIRECTS", 3)

    def handler(request):
        # Always redirect to the same place -- an infinite redirect loop.
        return httpx.Response(302, headers={"Location": "/start"})

    with pytest.raises(tp.PolicyDeniedError) as exc_info:
        await tp.secure_fetch("https://example.com/start", transport=_transport(handler))
    assert exc_info.value.reason_code == tp.DenyReason.REDIRECT_NOT_ALLOWED


async def test_response_below_limit_succeeds(monkeypatch):
    monkeypatch.setattr(tp, "MAX_FETCH_RESPONSE_BYTES", 100)

    def handler(request):
        return httpx.Response(200, content=b"x" * 50)

    result = await tp.secure_fetch("https://example.com/small", transport=_transport(handler))
    assert len(result.content) == 50


async def test_response_above_limit_is_blocked(monkeypatch):
    monkeypatch.setattr(tp, "MAX_FETCH_RESPONSE_BYTES", 100)

    def handler(request):
        return httpx.Response(200, content=b"x" * 5000)

    with pytest.raises(tp.PolicyDeniedError) as exc_info:
        await tp.secure_fetch("https://example.com/big", transport=_transport(handler))
    assert exc_info.value.reason_code == tp.DenyReason.RESPONSE_TOO_LARGE


async def test_fetch_timeout_produces_controlled_failure(monkeypatch):
    monkeypatch.setattr(tp, "FETCH_TIMEOUT_SECONDS", 0.1)

    async def slow_handler(request):
        await asyncio.sleep(5)
        return httpx.Response(200, text="too slow")  # pragma: no cover

    with pytest.raises(tp.PolicyDeniedError) as exc_info:
        await tp.secure_fetch("https://example.com/slow", transport=_transport(slow_handler))
    assert exc_info.value.reason_code == tp.DenyReason.FETCH_TIMEOUT
