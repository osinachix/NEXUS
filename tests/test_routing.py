import pytest
from pydantic import ValidationError

import main


@pytest.mark.parametrize("category", ["emotional", "logical", "math", "coding"])
def test_message_classifier_accepts_valid_categories(category):
    classifier = main.MessageClassifier(message_type=category)
    assert classifier.message_type == category


def test_message_classifier_rejects_invalid_category():
    with pytest.raises(ValidationError):
        main.MessageClassifier(message_type="not-a-real-category")


@pytest.mark.parametrize(
    "message_type,expected_route",
    [
        ("emotional", "counselor"),
        ("logical", "logical"),
        ("math", "math"),
        ("coding", "coding"),
    ],
)
def test_router_deterministic_mapping(message_type, expected_route):
    assert main.router({"message_type": message_type}) == {"route": expected_route}


def test_router_falls_back_to_logical_when_message_type_is_none():
    assert main.router({"message_type": None}) == {"route": "logical"}


def test_router_falls_back_to_logical_for_unknown_category():
    # Defensive branch: MessageClassifier's own validation means this should
    # never happen in practice, but router() must not crash if it does.
    assert main.router({"message_type": "unknown-category"}) == {"route": "logical"}
