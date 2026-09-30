import main


class _FakeMessage:
    def __init__(self, content):
        self.content = content


def test_classify_message_sets_message_type_from_classifier(monkeypatch):
    monkeypatch.setattr(
        main,
        "_call_classifier",
        lambda messages: main.MessageClassifier(message_type="math"),
    )
    state = {"messages": [_FakeMessage("what is 2+2?")]}

    result = main.classify_message(state)

    assert result == {"message_type": "math"}


def test_classify_message_falls_back_to_default_route_on_failure(monkeypatch):
    def _boom(messages):
        raise RuntimeError("provider is down")

    monkeypatch.setattr(main, "_call_classifier", _boom)
    state = {"messages": [_FakeMessage("hello")]}

    result = main.classify_message(state)

    # No crash, no fabricated category: message_type stays None so router()
    # falls back to its default route.
    assert result == {"message_type": None}
    assert main.router(result) == {"route": "logical"}
