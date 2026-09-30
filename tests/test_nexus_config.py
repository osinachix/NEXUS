"""Tests for config.py -- NEXUS's centralized, validated Phase 5
configuration (NOT tests/test_config.py, which covers main.py's model-name
resolution; a different, older concern)."""

import pytest

import config as config_module


def test_defaults_to_development_with_auth_disabled():
    cfg = config_module.load_config({})
    assert cfg.environment == "development"
    assert cfg.api_token is None
    assert cfg.auth_enabled is False
    assert cfg.database_url is None
    assert cfg.uses_postgres is False


def test_token_configured_enables_auth():
    cfg = config_module.load_config({"NEXUS_API_TOKEN": "secret-token"})
    assert cfg.auth_enabled is True
    assert cfg.api_token == "secret-token"


def test_production_without_token_is_a_hard_error():
    with pytest.raises(config_module.ConfigError, match="NEXUS_API_TOKEN"):
        config_module.load_config({"NEXUS_ENVIRONMENT": "production"})


def test_production_with_token_is_valid():
    cfg = config_module.load_config(
        {"NEXUS_ENVIRONMENT": "production", "NEXUS_API_TOKEN": "secret-token"}
    )
    assert cfg.environment == "production"
    assert cfg.auth_enabled is True


def test_unknown_environment_is_rejected():
    with pytest.raises(config_module.ConfigError, match="NEXUS_ENVIRONMENT"):
        config_module.load_config({"NEXUS_ENVIRONMENT": "staging-typo"})


def test_test_environment_does_not_require_a_token():
    cfg = config_module.load_config({"NEXUS_ENVIRONMENT": "test"})
    assert cfg.environment == "test"
    assert cfg.auth_enabled is False


def test_database_url_configures_postgres_mode():
    cfg = config_module.load_config(
        {"NEXUS_DATABASE_URL": "postgresql://user:pass@localhost:5432/nexus"}
    )
    assert cfg.uses_postgres is True
    assert cfg.database_url == "postgresql://user:pass@localhost:5432/nexus"


def test_rate_limit_defaults():
    cfg = config_module.load_config({})
    assert cfg.rate_limit_requests == config_module.DEFAULT_RATE_LIMIT_REQUESTS
    assert cfg.rate_limit_window_seconds == config_module.DEFAULT_RATE_LIMIT_WINDOW_SECONDS


def test_rate_limit_overrides_from_env():
    cfg = config_module.load_config(
        {"NEXUS_RATE_LIMIT_REQUESTS": "10", "NEXUS_RATE_LIMIT_WINDOW_SECONDS": "5"}
    )
    assert cfg.rate_limit_requests == 10
    assert cfg.rate_limit_window_seconds == 5.0


@pytest.mark.parametrize("value", ["not-a-number", "0", "-5"])
def test_invalid_rate_limit_requests_is_rejected(value):
    with pytest.raises(config_module.ConfigError, match="NEXUS_RATE_LIMIT_REQUESTS"):
        config_module.load_config({"NEXUS_RATE_LIMIT_REQUESTS": value})


@pytest.mark.parametrize("value", ["not-a-number", "0", "-1"])
def test_invalid_rate_limit_window_is_rejected(value):
    with pytest.raises(config_module.ConfigError, match="NEXUS_RATE_LIMIT_WINDOW_SECONDS"):
        config_module.load_config({"NEXUS_RATE_LIMIT_WINDOW_SECONDS": value})


def test_empty_token_string_is_treated_as_unset():
    # A blank env var (e.g. NEXUS_API_TOKEN= in a .env file) should behave
    # like the variable isn't set at all, not like an empty valid token.
    cfg = config_module.load_config({"NEXUS_API_TOKEN": ""})
    assert cfg.api_token is None
    assert cfg.auth_enabled is False


def test_config_error_messages_never_contain_token_value():
    # ConfigError is raised for production-without-token; the message must
    # describe the problem, never echo a (non-existent, here) secret value.
    try:
        config_module.load_config({"NEXUS_ENVIRONMENT": "production"})
        assert False, "expected ConfigError"
    except config_module.ConfigError as exc:
        assert "NEXUS_API_TOKEN" in str(exc)
