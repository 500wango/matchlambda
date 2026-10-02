import hmac
import hashlib
import json
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple


def sort_json_keys(obj: Any) -> Any:
    """
    Recursively sort dictionary keys for canonical JSON serialization
    according to NOWPayments IPN specification.
    Preserves list order and scalar values.
    """
    if isinstance(obj, dict):
        return {k: sort_json_keys(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, list):
        return [sort_json_keys(elem) for elem in obj]
    return obj


def canonical_json_dumps(data: Dict[str, Any]) -> str:
    """
    Serializes data to canonical JSON representation with sorted keys and no extraneous whitespace.
    """
    sorted_data = sort_json_keys(data)
    return json.dumps(sorted_data, separators=(",", ":"), ensure_ascii=False)


def verify_nowpayments_signature(payload_data: Dict[str, Any], signature: str, secret: str) -> bool:
    """
    Verifies HMAC-SHA512 signature against the canonical JSON of payload_data.
    """
    if not signature or not secret:
        return False
    canonical_body = canonical_json_dumps(payload_data)
    computed_sig = hmac.new(
        secret.encode("utf-8"),
        canonical_body.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(computed_sig.lower(), signature.strip().lower())
