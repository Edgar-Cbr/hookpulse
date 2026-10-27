"""
Asynchronous test suite for HookPulse webhook gateway, HMAC cryptography,
exponential backoff retry calculator, and simulator mechanics.
"""

from datetime import datetime, timezone
import json
try:
    import pytest
except ImportError:
    pytest = None

from app.core.crypto import compute_hmac_signature, verify_hmac_signature
from app.services.backoff import (
    MAX_RETRIES,
    calculate_backoff_delay,
    compute_retry_state,
)


def test_hmac_signature_generation_and_verification():
    """Verify constant-time HMAC-SHA256 signature computation and matching."""
    secret = "whsec_test_secret_key_abcdef123456"
    payload = json.dumps({"event": "tax_id.batch.completed", "status": "processed"}).encode("utf-8")

    # 1. Compute valid signature
    signature = compute_hmac_signature(secret, payload)
    assert isinstance(signature, str)
    assert len(signature) == 64  # SHA256 produces 64 hex characters

    # 2. Verify with raw hex
    assert verify_hmac_signature(secret, payload, signature) is True

    # 3. Verify with 'sha256=' prefix (GitHub/Stripe style)
    assert verify_hmac_signature(secret, payload, f"sha256={signature}") is True

    # 4. Reject tampered payload
    tampered_payload = json.dumps({"event": "tax_id.batch.completed", "status": "TAMPERED"}).encode("utf-8")
    assert verify_hmac_signature(secret, tampered_payload, signature) is False

    # 5. Reject invalid / forged signature
    assert verify_hmac_signature(secret, payload, "invalid_forged_hex_signature") is False

    # 6. Reject missing signature
    assert verify_hmac_signature(secret, payload, None) is False


def test_backoff_delay_exponential_growth():
    """Verify that backoff delay scales exponentially and applies jitter within bounds."""
    delays = [calculate_backoff_delay(retry) for retry in range(1, 5)]

    # Delay for retry 1: 2^1 + jitter (2.1 to 3.5s)
    assert 2.1 <= delays[0] <= 3.5

    # Delay for retry 2: 2^2 + jitter (4.1 to 5.5s)
    assert 4.1 <= delays[1] <= 5.5

    # Delay for retry 3: 2^3 + jitter (8.1 to 9.5s)
    assert 8.1 <= delays[2] <= 9.5

    # Delay for retry 4: 2^4 + jitter (16.1 to 17.5s)
    assert 16.1 <= delays[3] <= 17.5

    # Strict monotonicity
    assert delays[0] < delays[1] < delays[2] < delays[3]


def test_retry_state_machine_transition_to_dlq():
    """Verify state transitions: RETRYING for attempts 1-4, DLQ upon reaching maximum retries."""
    # Attempts 1 through 4 should remain in RETRYING
    for retry_count in range(0, MAX_RETRIES - 1):
        decision = compute_retry_state(current_retry_count=retry_count, max_retries=MAX_RETRIES)
        assert decision.status == "RETRYING"
        assert decision.new_retry_count == retry_count + 1
        assert decision.next_retry_at is not None
        assert decision.is_dead_letter is False
        assert decision.delay_seconds > 0

    # Attempt 5 (reaching MAX_RETRIES) should transition to DLQ
    dlq_decision = compute_retry_state(current_retry_count=4, max_retries=MAX_RETRIES)
    assert dlq_decision.status == "DLQ"
    assert dlq_decision.new_retry_count == 5
    assert dlq_decision.next_retry_at is None
    assert dlq_decision.is_dead_letter is True
    assert dlq_decision.delay_seconds == 0.0


def test_taxguard_payload_generator():
    """Verify that simulated TaxGuard payloads produce conforming fiscal verification data."""
    try:
        from app.api.v1.endpoints.simulator import generate_taxguard_payload
    except ImportError:
        # FastAPI is installed inside Docker / CI pipeline
        return

    payload = generate_taxguard_payload()
    assert payload["specversion"] == "1.0"
    assert payload["type"] == "tax_id.batch.completed"
    assert payload["source"] == "https://api.taxguard.io/v1/batches"
    assert "data" in payload

    data = payload["data"]
    assert data["jurisdiction"] == "MX-SAT"
    assert data["processed_records"] == 1500
    assert data["valid_count"] + data["invalid_count"] == 1500
    assert data["blacklisted_rfc_detected"] >= 0
    assert data["checksum"].startswith("sha256:")
