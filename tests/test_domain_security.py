"""Domain allowlist: exact-host matching only. Must not fall for the
classic `evil-example.com` / `example.com.evil.com` suffix tricks a naive
`.endswith()`-based check would allow through.
"""

import tool_policy as tp


def test_allowed_domain_is_permitted(monkeypatch):
    monkeypatch.setattr(tp, "ALLOWED_FETCH_DOMAINS", ("example.com",))
    assert tp.check_domain_allowlist("example.com").allowed


def test_domain_not_on_allowlist_is_denied(monkeypatch):
    monkeypatch.setattr(tp, "ALLOWED_FETCH_DOMAINS", ("example.com",))
    decision = tp.check_domain_allowlist("not-allowed.example")
    assert not decision.allowed
    assert decision.reason_code == tp.DenyReason.HOST_NOT_ALLOWED


def test_prefix_trick_does_not_match(monkeypatch):
    monkeypatch.setattr(tp, "ALLOWED_FETCH_DOMAINS", ("example.com",))
    assert not tp.check_domain_allowlist("evil-example.com").allowed


def test_suffix_trick_does_not_match(monkeypatch):
    monkeypatch.setattr(tp, "ALLOWED_FETCH_DOMAINS", ("example.com",))
    assert not tp.check_domain_allowlist("example.com.evil.com").allowed


def test_subdomains_are_not_included_by_default(monkeypatch):
    # Documented behavior (README/SECURITY.md): add each subdomain
    # explicitly if it should be allowed. This is what stops
    # "prefer exact host matching initially" from silently becoming
    # suffix matching by accident.
    monkeypatch.setattr(tp, "ALLOWED_FETCH_DOMAINS", ("example.com",))
    assert not tp.check_domain_allowlist("sub.example.com").allowed


def test_empty_allowlist_means_no_domain_restriction(monkeypatch):
    monkeypatch.setattr(tp, "ALLOWED_FETCH_DOMAINS", ())
    assert tp.check_domain_allowlist("literally-anything.example").allowed


def test_matching_is_case_insensitive(monkeypatch):
    monkeypatch.setattr(tp, "ALLOWED_FETCH_DOMAINS", ("example.com",))
    assert tp.check_domain_allowlist("EXAMPLE.COM").allowed


def test_multiple_domains_can_be_allowlisted(monkeypatch):
    monkeypatch.setattr(tp, "ALLOWED_FETCH_DOMAINS", ("example.com", "docs.example.com"))
    assert tp.check_domain_allowlist("example.com").allowed
    assert tp.check_domain_allowlist("docs.example.com").allowed
    assert not tp.check_domain_allowlist("other.example.com").allowed
