"""URL security: scheme, credentials, malformed URLs, and SSRF/private-
address blocking for `tool_policy.check_url`.

Hostname-based cases use the `fake_dns` fixture (see conftest.py) so these
tests never need real network/DNS access. Literal-IP cases (127.0.0.1,
169.254.169.254, ...) resolve locally on every platform without a network
query, so they don't need faking.
"""

import pytest

import tool_policy as tp


@pytest.fixture(autouse=True)
def _default_policy(monkeypatch):
    monkeypatch.setattr(tp, "ALLOWED_FETCH_SCHEMES", ("https",))
    monkeypatch.setattr(tp, "ALLOWED_FETCH_DOMAINS", ())


async def test_https_to_public_host_is_allowed(fake_dns):
    fake_dns({"example.com": ["93.184.216.34"]})
    decision = await tp.check_url("https://example.com/page")
    assert decision.allowed


async def test_http_is_blocked_by_default(fake_dns):
    fake_dns({"example.com": ["93.184.216.34"]})
    decision = await tp.check_url("http://example.com/page")
    assert not decision.allowed
    assert decision.reason_code == tp.DenyReason.SCHEME_NOT_ALLOWED


async def test_http_can_be_enabled_via_documented_dev_configuration(monkeypatch, fake_dns):
    # STEP 2's documented escape hatch: HTTP off by default, explicit opt-in.
    monkeypatch.setattr(tp, "ALLOWED_FETCH_SCHEMES", ("https", "http"))
    fake_dns({"example.com": ["93.184.216.34"]})
    decision = await tp.check_url("http://example.com/page")
    assert decision.allowed


@pytest.mark.parametrize(
    "url",
    [
        "https://localhost/",
        "https://127.0.0.1/",
        "https://[::1]/",
        "https://10.1.2.3/",
        "https://172.16.5.5/",
        "https://172.31.255.255/",
        "https://192.168.1.1/",
        "https://169.254.169.254/latest/meta-data/",
    ],
)
async def test_private_loopback_and_metadata_addresses_are_blocked(url, fake_dns):
    fake_dns({"localhost": ["127.0.0.1"]})
    decision = await tp.check_url(url)
    assert not decision.allowed
    assert decision.reason_code == tp.DenyReason.PRIVATE_ADDRESS


async def test_public_ip_literal_is_allowed(fake_dns):
    decision = await tp.check_url("https://8.8.8.8/")
    assert decision.allowed


async def test_malformed_url_is_blocked():
    decision = await tp.check_url("not a url at all")
    assert not decision.allowed
    assert decision.reason_code == tp.DenyReason.MALFORMED_URL


async def test_url_with_invalid_port_is_blocked():
    decision = await tp.check_url("https://example.com:not-a-port/")
    assert not decision.allowed
    assert decision.reason_code == tp.DenyReason.MALFORMED_URL


async def test_url_with_embedded_credentials_is_blocked(fake_dns):
    fake_dns({"example.com": ["93.184.216.34"]})
    decision = await tp.check_url("https://user:password@example.com/")
    assert not decision.allowed
    assert decision.reason_code == tp.DenyReason.CREDENTIALS_IN_URL


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/file",
        "gopher://example.com/",
        "data:text/plain;base64,aGVsbG8=",
        "javascript://alert(1)",
    ],
)
async def test_unsupported_schemes_are_blocked(url):
    decision = await tp.check_url(url)
    assert not decision.allowed
    # Some of these (e.g. data:, file:///) have no parseable host and are
    # caught as malformed before the scheme is even checked; either
    # classification is a correct denial.
    assert decision.reason_code in (tp.DenyReason.SCHEME_NOT_ALLOWED, tp.DenyReason.MALFORMED_URL)


async def test_dns_resolution_failure_is_a_controlled_denial(fake_dns):
    fake_dns({})  # nothing resolves
    decision = await tp.check_url("https://does-not-exist.invalid/")
    assert not decision.allowed
    assert decision.reason_code == tp.DenyReason.DNS_RESOLUTION_FAILED
