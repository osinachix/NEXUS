import asyncio
import json
import time

import anthropic
import httpx
import pytest

import main


class _FakeMessage:
    def __init__(self, content):
        self.content = content


def _rate_limit_error() -> anthropic.RateLimitError:
    return anthropic.RateLimitError(
        "rate limited",
        response=httpx.Response(429, request=httpx.Request("POST", "https://api.anthropic.com")),
        body=None,
    )


def _connection_error() -> anthropic.APIConnectionError:
    return anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))


def _patch_llm_invoke(monkeypatch, fake_invoke):
    # `main.llm` is a pydantic BaseModel (ChatAnthropic): it rejects
    # `setattr(instance, "invoke", ...)` for anything that isn't a declared
    # field. Patch the bound method on the class instead, which pytest's
    # monkeypatch cleanly restores after the test.
    monkeypatch.setattr(
        type(main.llm), "invoke", lambda self, messages, **kwargs: fake_invoke(messages)
    )


@pytest.fixture(autouse=True)
def _no_real_backoff_delay(monkeypatch):
    # Retries are real (bounded, exponential+jitter) but tests shouldn't
    # actually wait for them.
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    async def _instant_sleep(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", _instant_sleep)


def test_call_llm_retries_transient_error_then_succeeds(monkeypatch):
    attempts = []

    def _flaky_invoke(messages):
        attempts.append(messages)
        if len(attempts) < 2:
            raise _connection_error()
        return _FakeMessage("ok")

    _patch_llm_invoke(monkeypatch, _flaky_invoke)

    result = main._call_llm([{"role": "user", "content": "hi"}])

    assert result.content == "ok"
    assert len(attempts) == 2


def test_call_llm_does_not_retry_non_transient_errors(monkeypatch):
    attempts = []

    def _always_boom(messages):
        attempts.append(messages)
        raise ValueError("not a provider/transport error")

    _patch_llm_invoke(monkeypatch, _always_boom)

    with pytest.raises(ValueError):
        main._call_llm([{"role": "user", "content": "hi"}])

    assert len(attempts) == 1  # no retry attempted


def test_call_llm_gives_up_after_bounded_attempts(monkeypatch, caplog):
    attempts = []

    def _always_transient(messages):
        attempts.append(messages)
        raise _rate_limit_error()

    _patch_llm_invoke(monkeypatch, _always_transient)

    with pytest.raises(anthropic.RateLimitError):
        main._call_llm([{"role": "user", "content": "hi"}])

    assert len(attempts) == main.LLM_MAX_ATTEMPTS
    retry_logs = [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "multi_agent_router"
    ]
    assert len(retry_logs) == main.LLM_MAX_ATTEMPTS - 1
    assert all(log["event_type"] == "provider_retry" for log in retry_logs)
    assert all(log["error_type"] == "RateLimitError" for log in retry_logs)
    assert all("rate limited" not in record.getMessage() for record in caplog.records)


def test_fallback_reply_does_not_log_exception_details(caplog):
    caplog.set_level("ERROR", logger="multi_agent_router")

    result = main._fallback_reply()

    assert result == {"messages": [{"role": "assistant", "content": main.GENERIC_FAILURE_MESSAGE}]}
    assert not caplog.records


def test_counselor_agent_returns_safe_message_on_persistent_provider_failure(monkeypatch):
    def _always_boom(messages):
        raise _rate_limit_error()

    monkeypatch.setattr(main, "_call_llm", _always_boom)
    state = {"messages": [_FakeMessage("I'm having a rough day")]}

    result = main.counselor_agent(state)

    assert result["messages"][0]["content"] == main.GENERIC_FAILURE_MESSAGE


async def test_logical_agent_returns_safe_message_when_agent_unavailable(monkeypatch):
    monkeypatch.setattr(main, "logical_react_agent", None)
    state = {"messages": [_FakeMessage("what's the capital of France?")]}

    result = await main.logical_agent(state)

    assert result["messages"][0]["content"] == main.GENERIC_FAILURE_MESSAGE


async def test_call_logical_agent_retries_transient_error_then_succeeds(monkeypatch):
    attempts = []

    class _FakeAgent:
        async def ainvoke(self, payload, config=None):
            attempts.append(payload)
            if len(attempts) < 2:
                raise _connection_error()
            return {"messages": [_FakeMessage("fetched result")]}

    monkeypatch.setattr(main, "logical_react_agent", _FakeAgent())

    result = await main._call_logical_agent("look this up")

    assert result["messages"][-1].content == "fetched result"
    assert len(attempts) == 2
