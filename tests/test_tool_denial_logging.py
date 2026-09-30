"""Log security for blocked/denied tool requests specifically (Phase 2):
`tool_denied` events must carry only a stable reason code and identifiers
-- never credentials, authorization headers, full URLs with query strings,
or fetched content.
"""

import json

import httpx
import pytest
from langchain_core.tools import tool

import main
import tool_policy as tp


def _events_from(caplog):
    events = []
    for record in caplog.records:
        if record.name != "nexus.observability":
            continue
        try:
            events.append(json.loads(record.getMessage()))
        except (TypeError, ValueError):
            continue
    return events


@pytest.fixture(autouse=True)
def _policy_defaults(monkeypatch, fake_dns):
    monkeypatch.setattr(tp, "ALLOWED_FETCH_SCHEMES", ("https",))
    monkeypatch.setattr(tp, "ALLOWED_FETCH_DOMAINS", ())
    fake_dns({"example.com": ["93.184.216.34"]})


async def test_denied_credentialed_url_never_logs_the_credentials(caplog):
    caplog.set_level("INFO", logger="nexus.observability")
    secret_password = "sk-ant-SUPER-SECRET-PASSWORD"  # nosec: test fixture only

    instrumented = main._instrument_tool(main.fetch, agent_name="logical")
    raw = await instrumented.ainvoke(
        {"url": f"https://user:{secret_password}@example.com/"},
        config={"configurable": {"request_id": "r1", "thread_id": "t1"}},
    )

    payload = json.loads(raw)
    assert payload["trust"] == "untrusted"
    assert secret_password not in caplog.text
    assert secret_password not in raw

    events = _events_from(caplog)
    denied = [e for e in events if e["event_type"] == "tool_denied"]
    assert denied
    assert denied[0]["reason"] == tp.DenyReason.CREDENTIALS_IN_URL


async def test_denied_url_with_sensitive_query_param_is_not_logged(caplog):
    caplog.set_level("INFO", logger="nexus.observability")
    secret_token = "session_token=abc123SECRETXYZ"

    instrumented = main._instrument_tool(main.fetch, agent_name="logical")
    # A private-address URL, deliberately carrying a sensitive-looking
    # query string, to confirm the query string never reaches the logs.
    await instrumented.ainvoke(
        {"url": f"https://169.254.169.254/latest/meta-data/?{secret_token}"},
        config={"configurable": {"request_id": "r2", "thread_id": "t2"}},
    )

    assert secret_token not in caplog.text
    assert "abc123SECRETXYZ" not in caplog.text


async def test_tool_not_authorized_denial_does_not_leak_url_details(caplog):
    caplog.set_level("INFO", logger="nexus.observability")

    @tool("fetch")
    async def _fake_fetch(url: str) -> str:
        """Fake fetch tool."""
        return f"content of {url}"

    instrumented = main._instrument_tool(_fake_fetch, agent_name="coding")  # not authorized
    sensitive_url = "https://internal.example/admin?token=abcSECRET"
    await instrumented.ainvoke(
        {"url": sensitive_url},
        config={"configurable": {"request_id": "r3", "thread_id": "t3"}},
    )

    assert "abcSECRET" not in caplog.text
    assert sensitive_url not in caplog.text


async def test_response_too_large_denial_does_not_log_fetched_content(caplog, monkeypatch):
    caplog.set_level("INFO", logger="nexus.observability")
    monkeypatch.setattr(tp, "MAX_FETCH_RESPONSE_BYTES", 10)
    secret_in_body = "TOP-SECRET-PAGE-CONTENT"

    def handler(request):
        return httpx.Response(200, text=secret_in_body * 10)

    real_secure_fetch = tp.secure_fetch

    async def _secure_fetch(url, **kwargs):
        return await real_secure_fetch(url, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(tp, "secure_fetch", _secure_fetch)

    instrumented = main._instrument_tool(main.fetch, agent_name="logical")
    await instrumented.ainvoke(
        {"url": "https://example.com/big"},
        config={"configurable": {"request_id": "r4", "thread_id": "t4"}},
    )

    assert secret_in_body not in caplog.text
