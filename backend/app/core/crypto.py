import hashlib
import hmac
import secrets
from typing import Optional


def compute_hmac_signature(secret: str, raw_body: bytes) -> str:
    """
    Computes HMAC-SHA256 hexdigest for the given secret and raw body bytes.
    """
    key = secret.encode("utf-8")
    return hmac.new(key, raw_body, hashlib.sha256).hexdigest()


def verify_hmac_signature(
    secret: str,
    raw_body: bytes,
    provided_sig: Optional[str],
) -> bool:
    """
    Verifies HMAC-SHA256 signature in constant time using hmac.compare_digest.
    Supports raw hex strings or 'sha256=<hex>' prefix formats.
    Returns False if signature is missing or does not match.
    """
    if not provided_sig or not secret:
        return False

    normalized_sig = provided_sig.strip()
    if normalized_sig.startswith("sha256="):
        normalized_sig = normalized_sig[7:]

    expected_sig = compute_hmac_signature(secret, raw_body)

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(normalized_sig.lower(), expected_sig.lower())


def generate_signing_secret(prefix: str = "whsec_") -> str:
    """
    Generates a secure cryptographically random signing secret with standard prefix.
    """
    return f"{prefix}{secrets.token_hex(24)}"


def generate_endpoint_slug(name: str = "") -> str:
    """
    Generates a unique endpoint slug based on name or random hex.
    """
    clean_name = "".join(c.lower() if c.isalnum() else "_" for c in name).strip("_")
    short_uuid = secrets.token_hex(4)
    if clean_name:
        return f"ep_{clean_name[:24]}_{short_uuid}"
    return f"ep_{short_uuid}_{secrets.token_hex(2)}"
