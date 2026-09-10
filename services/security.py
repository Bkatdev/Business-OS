"""Security helpers that avoid external dependencies."""
from __future__ import annotations

import hashlib
import hmac
import re
import time

_SIGNATURE_RE = re.compile(r"^v=(\d+),d=([0-9a-fA-F]+)$")


def verify_retell_signature(raw_body: bytes, signature: str, api_key: str, tolerance_ms: int = 300_000):
    """Verify Retell's timestamped HMAC-SHA256 webhook signature.

    Returns (ok, reason). The raw request bytes are required so JSON whitespace or
    key order cannot change the signed payload.
    """
    if not api_key:
        return False, "RETELL_API_KEY is not configured."
    if not signature:
        return False, "X-Retell-Signature header is missing."

    match = _SIGNATURE_RE.match(signature.strip())
    if not match:
        return False, "X-Retell-Signature format is invalid."

    timestamp_text, supplied_digest = match.groups()
    timestamp_ms = int(timestamp_text)
    now_ms = int(time.time() * 1000)
    if abs(now_ms - timestamp_ms) > tolerance_ms:
        return False, "Webhook signature timestamp is outside the allowed replay window."

    signed = raw_body + timestamp_text.encode("utf-8")
    expected = hmac.new(api_key.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected.lower(), supplied_digest.lower()):
        return False, "Webhook signature did not match."
    return True, "Webhook signature verified."
