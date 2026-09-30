"""Tests for auth.py -- HTTP-boundary authentication (Phase 5).

Pure unit tests against `auth.authenticate()`; no FastAPI app involved
(see tests/test_api_auth.py for the end-to-end HTTP-level behavior)."""

import pytest

import access
import auth


def test_development_mode_returns_fixed_principal_when_no_token_configured():
    principal = auth.authenticate(None, configured_token=None)
    assert principal.principal_id == access.LOCAL_API_PRINCIPAL
    assert principal.authentication_method == "development_mode"


def test_development_mode_ignores_any_header_sent():
    # No token configured means auth is off entirely -- even a garbage
    # header doesn't change the outcome.
    principal = auth.authenticate("Bearer whatever", configured_token=None)
    assert principal.authentication_method == "development_mode"


def test_valid_bearer_token_is_authenticated():
    principal = auth.authenticate("Bearer correct-token", configured_token="correct-token")
    assert principal.authentication_method == "bearer_token"
    assert principal.principal_id.startswith("token-")


def test_same_token_always_yields_the_same_principal_id():
    p1 = auth.authenticate("Bearer correct-token", configured_token="correct-token")
    p2 = auth.authenticate("Bearer correct-token", configured_token="correct-token")
    assert p1.principal_id == p2.principal_id


def test_principal_id_never_contains_the_raw_token():
    principal = auth.authenticate("Bearer super-secret-value", configured_token="super-secret-value")
    assert "super-secret-value" not in principal.principal_id


def test_missing_header_is_rejected_when_token_configured():
    with pytest.raises(auth.AuthenticationError):
        auth.authenticate(None, configured_token="correct-token")


def test_empty_header_is_rejected_when_token_configured():
    with pytest.raises(auth.AuthenticationError):
        auth.authenticate("", configured_token="correct-token")


def test_wrong_token_is_rejected():
    with pytest.raises(auth.AuthenticationError):
        auth.authenticate("Bearer wrong-token", configured_token="correct-token")


@pytest.mark.parametrize(
    "header",
    [
        "Basic correct-token",  # wrong scheme
        "Bearer",  # scheme with nothing after it
        "Bearer ",  # scheme with only whitespace after it
        "Bearer correct-token extra-stuff",  # malformed (embedded space)
        "correct-token",  # no scheme at all
    ],
)
def test_malformed_authorization_header_is_rejected(header):
    with pytest.raises(auth.AuthenticationError):
        auth.authenticate(header, configured_token="correct-token")


def test_authentication_error_detail_never_contains_the_configured_token():
    try:
        auth.authenticate("Bearer wrong-token", configured_token="the-real-secret")
        assert False, "expected AuthenticationError"
    except auth.AuthenticationError as exc:
        assert "the-real-secret" not in exc.detail
        assert "wrong-token" not in exc.detail
