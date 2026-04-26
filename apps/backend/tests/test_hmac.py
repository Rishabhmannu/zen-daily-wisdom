from zen_backend.security.hmac_sig import sign_payload, verify_payload


def test_hmac_round_trip() -> None:
    secret = "test-secret"
    payload = b'{"hello":"world"}'
    sig = sign_payload(secret, payload)
    assert verify_payload(secret, payload, sig)
    assert not verify_payload(secret, b'{"hello":"tampered"}', sig)

