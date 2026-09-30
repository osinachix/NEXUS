"""Observability must not leak secrets: forbidden field names are stripped
defensively, and a full (mocked) execution carrying a planted "secret"
through both the user message and the model reply never surfaces it in any
captured log output.
"""

import json

import main
import observability
import runtime as nexus_runtime


def test_sanitize_strips_forbidden_keys_but_keeps_ordinary_metadata():
    cleaned = observability._sanitize({
        "api_key": "sk-ant-abc123",
        "anthropic_api_key": "sk-ant-def456",
        "authorization": "Bearer xyz",
        "password": "hunter2",
        "token": "abc.def.ghi",
        "content": "raw message text",
        "route": "math",  # ordinary metadata: must survive
        "tool": "fetch",  # ordinary metadata: must survive
    })
    assert cleaned == {"route": "math", "tool": "fetch"}


def test_log_event_never_emits_forbidden_fields(caplog):
    caplog.set_level("INFO", logger="nexus.observability")

    observability.log_event(
        "agent_completed",
        request_id="r1",
        thread_id="t1",
        api_key="sk-ant-should-not-appear",
        content="raw user message that should not appear",
    )

    assert "sk-ant-should-not-appear" not in caplog.text
    assert "raw user message that should not appear" not in caplog.text


def test_observability_failure_logs_only_safe_metadata(caplog, monkeypatch):
    planted_secret = "internal-logging-detail-SHOULD-NOT-LEAK"

    def _raise_with_secret(_message):
        raise RuntimeError(planted_secret)

    monkeypatch.setattr(observability.logger, "info", _raise_with_secret)
    caplog.set_level("WARNING", logger="nexus.observability")

    observability.log_event("agent_completed", request_id="r1", thread_id="t1")

    assert planted_secret not in caplog.text
    warning_records = [
        record for record in caplog.records if record.name == "nexus.observability"
    ]
    assert warning_records
    payload = json.loads(warning_records[-1].getMessage())
    assert payload == {
        "event_type": "observability_emit_failed",
        "source_event_type": "agent_completed",
        "error_type": "RuntimeError",
    }


class _FakeMessage:
    def __init__(self, content):
        self.content = content


async def test_full_execution_never_logs_a_planted_secret(tmp_path, caplog, monkeypatch):
    planted_secret = "sk-ant-PLANTED-SECRET-VALUE"  # nosec: test fixture, not a real key

    monkeypatch.setattr(
        main, "_call_classifier", lambda messages: main.MessageClassifier(message_type="coding")
    )
    monkeypatch.setattr(
        main, "_call_llm", lambda messages: _FakeMessage(f"reply containing {planted_secret}")
    )

    caplog.set_level("INFO")
    db_path = str(tmp_path / "sec.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        await session.execute(nexus_runtime.new_thread_id(), f"my key is {planted_secret}")

    assert planted_secret not in caplog.text
