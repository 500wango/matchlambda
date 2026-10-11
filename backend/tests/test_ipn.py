from app.services.nowpayments import verify_nowpayments_signature
from tests.ipn_sign import independent_ipn_signature


def test_production_verifier_accepts_independent_ascii_and_non_ascii():
    secret = "ipn-secret-for-canonical-check"
    payload = {
        "order_id": "MLQ_1",
        "payment_status": "finished",
        "pay_currency": "USDTTRC20",
        "note": "café",
        "nested": {"b": 2, "a": 1},
    }
    signature = independent_ipn_signature(payload, secret)
    assert verify_nowpayments_signature(payload, signature, secret) is True
    assert verify_nowpayments_signature(payload, "0" * 64, secret) is False
