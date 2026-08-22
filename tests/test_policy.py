"""RetryPolicy tests (v0.1.2): bounded retries, no semantic retries."""

from __future__ import annotations

import pytest

from control.policy import RetryPolicy


def test_run_returns_value_and_does_not_sleep_on_success() -> None:
    sleeps: list[float] = []
    policy = RetryPolicy(max_retries=3)
    result = policy.run(lambda: "ok", sleeper=sleeps.append)
    assert result == "ok"
    assert sleeps == []


def test_run_retries_transient_failures_then_succeeds() -> None:
    sleeps: list[float] = []
    attempts = {"n": 0}

    def flaky() -> str:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise OSError("daemon busy")
        return "recovered"

    policy = RetryPolicy(max_retries=3)
    assert policy.run(flaky, sleeper=sleeps.append) == "recovered"
    assert attempts["n"] == 3
    assert len(sleeps) == 2  # one backoff per retry, none after success


def test_run_is_bounded_and_reraises_last_error() -> None:
    attempts = {"n": 0}

    def always_fails() -> None:
        attempts["n"] += 1
        raise OSError("still down")

    policy = RetryPolicy(max_retries=2)
    with pytest.raises(OSError, match="still down"):
        policy.run(always_fails, sleeper=lambda _s: None)
    assert attempts["n"] == 3  # 1 initial attempt + 2 retries


def test_run_only_retries_matching_exception_types() -> None:
    attempts = {"n": 0}

    def bad_request() -> None:
        attempts["n"] += 1
        raise ValueError("semantic error, do not retry")

    policy = RetryPolicy(max_retries=3)
    with pytest.raises(ValueError, match="semantic"):
        policy.run(bad_request, retry_on=OSError, sleeper=lambda _s: None)
    assert attempts["n"] == 1
