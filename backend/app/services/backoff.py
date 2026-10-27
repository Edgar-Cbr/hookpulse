"""
Exponential Backoff with Full Jitter and Dead Letter Queue (DLQ) state transition logic.
Implements the HookPulse core retry calculation strategy adhering to Section 4.2 of BLUEPRINT.md.
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import logging
import random
from typing import Optional

logger = logging.getLogger("hookpulse.backoff")

MAX_RETRIES: int = 5
DEFAULT_BASE: float = 2.0
MIN_JITTER: float = 0.1
MAX_JITTER: float = 1.5


@dataclass
class RetryDecision:
    """Represents the computed next state of a webhook delivery attempt."""
    status: str
    new_retry_count: int
    next_retry_at: Optional[datetime]
    delay_seconds: float
    is_dead_letter: bool


def calculate_backoff_delay(
    retry_count: int,
    base: float = DEFAULT_BASE,
    min_jitter: float = MIN_JITTER,
    max_jitter: float = MAX_JITTER,
) -> float:
    """
    Calculates exponential backoff delay with uniform jitter.
    Formula: delay = (base ** retry_count) + random.uniform(min_jitter, max_jitter)
    """
    jitter = random.uniform(min_jitter, max_jitter)
    return round((base ** retry_count) + jitter, 3)


def compute_retry_state(
    current_retry_count: int,
    max_retries: int = MAX_RETRIES,
    base: float = DEFAULT_BASE,
    min_jitter: float = MIN_JITTER,
    max_jitter: float = MAX_JITTER,
) -> RetryDecision:
    """
    Evaluates whether an event should transition to RETRYING or DLQ.
    - If current_retry_count + 1 < max_retries:
        Status becomes 'RETRYING', next_retry_at is scheduled.
    - If current_retry_count + 1 >= max_retries:
        Status becomes 'DLQ', next_retry_at is cleared.
    """
    next_count = current_retry_count + 1

    if next_count >= max_retries:
        logger.info(
            f"Event reached maximum retries ({next_count}/{max_retries}). Transitioning to DLQ."
        )
        return RetryDecision(
            status="DLQ",
            new_retry_count=next_count,
            next_retry_at=None,
            delay_seconds=0.0,
            is_dead_letter=True,
        )

    delay = calculate_backoff_delay(
        retry_count=next_count,
        base=base,
        min_jitter=min_jitter,
        max_jitter=max_jitter,
    )
    next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)

    logger.debug(
        f"Scheduled retry {next_count}/{max_retries} with delay {delay:.2f}s at {next_retry_at.isoformat()}"
    )

    return RetryDecision(
        status="RETRYING",
        new_retry_count=next_count,
        next_retry_at=next_retry_at,
        delay_seconds=delay,
        is_dead_letter=False,
    )
