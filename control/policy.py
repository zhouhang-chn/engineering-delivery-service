"""Deterministic policies: retry, timeout, approval, idempotency.

Bounded autonomous retry and escalation-to-human rules live here as
primitives the Supervisor can invoke.
"""

DEFAULT_MAX_RETRIES = 3


class RetryPolicy:
    """Bounded retry rule shared by runtime, thread and deployment calls."""

    def __init__(self, max_retries: int = DEFAULT_MAX_RETRIES):
        self.max_retries = max_retries

    def should_retry(self, attempt: int) -> bool:
        """Return True while the attempt count is within the bound."""
        return attempt < self.max_retries
