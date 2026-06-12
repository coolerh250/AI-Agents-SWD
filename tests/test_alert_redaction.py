"""Stage 40 -- payload redaction tests."""

from shared.sdk.incidents.redaction import payload_hash, redact_payload


def test_redact_removes_token():
    payload = {"alert_name": "HostDown", "token": "super-secret-123"}
    result = redact_payload(payload)
    assert result["alert_name"] == "HostDown"
    assert result["token"] == "[REDACTED]"
    assert "super-secret-123" not in str(result)


def test_redact_removes_secret():
    payload = {"secret": "my-secret", "data": "ok"}
    result = redact_payload(payload)
    assert result["secret"] == "[REDACTED]"
    assert result["data"] == "ok"


def test_redact_removes_password():
    payload = {"password": "hunter2"}
    result = redact_payload(payload)
    assert result["password"] == "[REDACTED]"


def test_redact_removes_authorization():
    payload = {"authorization": "Bearer xyz", "source": "test"}
    result = redact_payload(payload)
    assert result["authorization"] == "[REDACTED]"
    assert result["source"] == "test"


def test_redact_removes_api_key():
    payload = {"api_key": "key-abc", "alert_name": "test"}
    result = redact_payload(payload)
    assert result["api_key"] == "[REDACTED]"


def test_redact_removes_webhook_secret():
    payload = {"webhook_secret": "ws-secret"}
    result = redact_payload(payload)
    assert result["webhook_secret"] == "[REDACTED]"


def test_redact_removes_access_token():
    payload = {"access_token": "at-123"}
    result = redact_payload(payload)
    assert result["access_token"] == "[REDACTED]"


def test_redact_removes_refresh_token():
    payload = {"refresh_token": "rt-456"}
    result = redact_payload(payload)
    assert result["refresh_token"] == "[REDACTED]"


def test_redact_removes_private_key():
    payload = {"private_key": "-----BEGIN RSA PRIVATE KEY-----"}
    result = redact_payload(payload)
    assert result["private_key"] == "[REDACTED]"


def test_redact_nested():
    payload = {"labels": {"token": "inner-secret", "name": "ok"}}
    result = redact_payload(payload)
    assert result["labels"]["token"] == "[REDACTED]"
    assert result["labels"]["name"] == "ok"


def test_payload_hash_deterministic():
    payload = {"a": 1, "b": "hello"}
    h1 = payload_hash(payload)
    h2 = payload_hash(payload)
    assert h1 == h2
    assert len(h1) == 64


def test_payload_hash_different_for_different_payloads():
    assert payload_hash({"a": 1}) != payload_hash({"a": 2})
