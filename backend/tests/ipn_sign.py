import hashlib
import hmac
import json
from typing import Any, Dict


def independent_ipn_signature(payload: Dict[str, Any], secret: str) -> str:
    """Sign the way the NOWPayments reference client does, without the app helper.

    sort_keys is recursive. ensure_ascii matches the production canonical form.
    """
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha512).hexdigest()
