"""Tests for rate_limit.py -- bounded, process-local, fixed-window rate
limiting (Phase 5). Pure unit tests against `RateLimiter` directly, with
`now` injected for determinism (see end-to-end HTTP tests in
tests/test_api_auth.py)."""

import pytest

import rate_limit


def test_requests_under_the_limit_succeed():
    limiter = rate_limit.RateLimiter(max_requests=3, window_seconds=60)
    for _ in range(3):
        result = limiter.check("principal-a", now=0.0)
        assert result.allowed is True


def test_exceeding_the_limit_is_denied():
    limiter = rate_limit.RateLimiter(max_requests=2, window_seconds=60)
    limiter.check("principal-a", now=0.0)
    limiter.check("principal-a", now=0.0)
    result = limiter.check("principal-a", now=0.0)
    assert result.allowed is False
    assert result.retry_after_seconds is not None
    assert result.retry_after_seconds > 0


def test_retry_after_shrinks_as_the_window_elapses():
    limiter = rate_limit.RateLimiter(max_requests=1, window_seconds=60)
    limiter.check("principal-a", now=0.0)
    early = limiter.check("principal-a", now=1.0)
    late = limiter.check("principal-a", now=50.0)
    assert early.retry_after_seconds > late.retry_after_seconds


def test_window_resets_after_it_elapses():
    limiter = rate_limit.RateLimiter(max_requests=1, window_seconds=10)
    assert limiter.check("principal-a", now=0.0).allowed is True
    assert limiter.check("principal-a", now=5.0).allowed is False
    # Window has fully elapsed -- a fresh window starts.
    assert limiter.check("principal-a", now=11.0).allowed is True


def test_principals_are_isolated_from_each_other():
    limiter = rate_limit.RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.check("principal-a", now=0.0).allowed is True
    # principal-a is now over its limit, but principal-b has its own window.
    assert limiter.check("principal-a", now=0.0).allowed is False
    assert limiter.check("principal-b", now=0.0).allowed is True


def test_store_stays_bounded_under_many_distinct_principals():
    limiter = rate_limit.RateLimiter(max_requests=5, window_seconds=60, max_principals=10)
    for i in range(1000):
        limiter.check(f"principal-{i}", now=0.0)
    assert limiter.tracked_principal_count() <= 10


def test_oldest_touched_principal_is_evicted_first():
    limiter = rate_limit.RateLimiter(max_requests=5, window_seconds=60, max_principals=2)
    limiter.check("principal-a", now=0.0)
    limiter.check("principal-b", now=0.0)
    limiter.check("principal-c", now=0.0)  # evicts principal-a
    assert limiter.tracked_principal_count() == 2
    # principal-a's window was evicted, so a fresh check starts a new one
    # (allowed again) rather than continuing to count against the old one.
    result = limiter.check("principal-a", now=0.0)
    assert result.allowed is True


@pytest.mark.parametrize("bad_kwargs", [{"max_requests": 0}, {"max_requests": -1}])
def test_non_positive_max_requests_is_rejected(bad_kwargs):
    with pytest.raises(ValueError):
        rate_limit.RateLimiter(window_seconds=60, **bad_kwargs)


def test_non_positive_window_is_rejected():
    with pytest.raises(ValueError):
        rate_limit.RateLimiter(max_requests=5, window_seconds=0)
