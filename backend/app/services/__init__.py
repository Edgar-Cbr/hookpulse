"""HookPulse background services and domain business logic."""

from app.services.backoff import (
    MAX_RETRIES,
    RetryDecision,
    calculate_backoff_delay,
    compute_retry_state,
)

try:
    from app.services.delivery_engine import dispatch_webhook_event, retry_worker_loop
except ImportError:
    dispatch_webhook_event = None  # type: ignore
    retry_worker_loop = None  # type: ignore

__all__ = [
    "MAX_RETRIES",
    "RetryDecision",
    "calculate_backoff_delay",
    "compute_retry_state",
    "dispatch_webhook_event",
    "retry_worker_loop",
]
