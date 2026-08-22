"""Deterministic policies: retry, timeout, approval, idempotency.

Bounded autonomous retry and escalation-to-human rules live here as
primitives the Supervisor can invoke.
"""

from __future__ import annotations

import time
from collections.abc import Callable

DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_S = 0.2


class RetryPolicy:
    """Bounded retry rule shared by runtime, thread and deployment calls."""

    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_s: float = DEFAULT_BACKOFF_S,
    ):
        self.max_retries = max_retries
        self.backoff_s = backoff_s

    def should_retry(self, attempt: int) -> bool:
        """Return True while the retry count is within the bound."""
        return attempt < self.max_retries

    def run(
        self,
        fn: Callable[[], object],
        *,
        retry_on: type[BaseException] | tuple[type[BaseException], ...] = Exception,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        """Call ``fn``, retrying matching errors until the bound is hit.

        Retries are operational only — transient infrastructure errors.
        Semantic failures must be excluded via ``retry_on`` so they
        surface on the first attempt.
        """
        retries = 0
        while True:
            try:
                return fn()
            except retry_on:
                if not self.should_retry(retries):
                    raise
                retries += 1
                sleeper(self.backoff_s)
