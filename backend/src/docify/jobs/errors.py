"""Job error taxonomy (Master Doc §8.3 rules 9–11)."""

from __future__ import annotations


class JobError(Exception):
    pass


class RetryableError(JobError):
    """Network blips, 5xx, rate limits. `delay_s` overrides exponential backoff (e.g. retry-after)."""

    def __init__(self, message: str, *, delay_s: int | None = None) -> None:
        super().__init__(message)
        self.delay_s = delay_s


class NonRetryableError(JobError):
    """Permanent problem (too large, permission revoked, invalid input). Shown to users."""

    def __init__(self, message: str, *, code: str = "failed", repo_status: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.repo_status = repo_status


class BudgetExceeded(JobError):
    """AI budget window is exhausted → job parks in `blocked_budget` until the window resets."""


class LeaseLost(JobError):
    """Another worker took over (fence changed). Stop immediately, write nothing."""
