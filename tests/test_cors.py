"""CORS (Phase 6.1): the NEXUS Console is a browser-based, separate-origin
client. Without explicit CORS headers, browsers block every cross-origin
request -- this was a genuine defect found only by running the real
Console against the real API in a real browser (curl/httpx never exercise
browser CORS enforcement). See api.py's CORSMiddleware setup.
"""

import httpx
import pytest

import main


class _FakeMessage:
    def __init__(self, content):
        self.content = content


@pytest.fixture(autouse=True)
def _fake_llm_calls(monkeypatch):
    monkeypatch.setattr(
        main, "_call_classifier", lambda messages: main.MessageClassifier(message_type="coding")
    )
    monkeypatch.setattr(main, "_call_llm", lambda messages: _FakeMessage("stub reply"))


@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_CHECKPOINT_DB", str(tmp_path / "cors_test.sqlite"))
    import api

    async with api.app.router.lifespan_context(api.app):
        transport = httpx.ASGITransport(app=api.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
            yield ac


async def test_default_console_origin_is_allowed(client):
    resp = await client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


async def test_unlisted_origin_is_not_granted_cors_headers(client):
    resp = await client.get("/health", headers={"Origin": "http://evil.example"})
    assert resp.status_code == 200  # the request itself still succeeds server-side...
    # ...but no CORS header authorizes a browser to let the page read it.
    assert "access-control-allow-origin" not in {k.lower() for k in resp.headers.keys()}


async def test_preflight_request_is_handled(client):
    resp = await client.options(
        "/v1/sessions",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
    allowed_headers = resp.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers


async def test_retry_after_is_exposed_for_cross_origin_reads(client):
    resp = await client.get("/health", headers={"Origin": "http://localhost:5173"})
    exposed = resp.headers.get("access-control-expose-headers", "")
    assert "Retry-After" in exposed


async def test_cors_headers_present_even_on_an_error_response(client):
    # Dev mode (no NEXUS_API_TOKEN) auto-authenticates every request, so
    # this legitimately reaches the ApiError(404) path, not a 401 -- CORS
    # headers must still be attached to that error response, since it's
    # exactly the kind of response CORSMiddleware needs to wrap (see
    # api.py's comment on middleware ordering).
    resp = await client.get(
        "/v1/runs/req-does-not-exist", headers={"Origin": "http://localhost:5173"}
    )
    assert resp.status_code == 404
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_custom_origins_are_read_from_environment(monkeypatch):
    monkeypatch.setenv("NEXUS_CONSOLE_ORIGINS", "https://console.example, https://other.example")
    import importlib

    import api

    importlib.reload(api)
    try:
        assert api._load_console_origins() == ["https://console.example", "https://other.example"]
    finally:
        monkeypatch.delenv("NEXUS_CONSOLE_ORIGINS", raising=False)
        importlib.reload(api)


def test_default_origins_cover_the_standard_vite_dev_ports(monkeypatch):
    monkeypatch.delenv("NEXUS_CONSOLE_ORIGINS", raising=False)
    import api

    origins = api._load_console_origins()
    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins
