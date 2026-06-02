import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

def test_create_preference_unauthorized(client):
    response = client.post("/api/v1/payments/create-preference", json={"plan_type": "pro"})
    assert response.status_code == 401
    assert "error" in response.json()
    assert "Debes iniciar sesión." in response.json()["error"]

@patch("app.api.v1.payments.ensure_user", new_callable=AsyncMock)
@patch("app.api.v1.payments.get_quota_status", new_callable=AsyncMock)
@patch("app.api.v1.payments.httpx.AsyncClient")
def test_create_preference_authorized(mock_http, mock_get_quota, mock_ensure_user, client):
    mock_get_quota.return_value = {"active_plan_type": "starter"}
    mock_ensure_user.return_value = None
    
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "init_point": "http://mp.com/init",
        "sandbox_init_point": "http://mp.com/sandbox",
        "id": "pref_123"
    }
    
    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_response
    mock_http.return_value.__aenter__.return_value = mock_client_instance

    with patch("fastapi.Request.session", new_callable=MagicMock) as mock_session:
        mock_session.get.side_effect = lambda key, default=None: {
            "user": {"email": "test@example.com", "name": "Test User"}
        }.get(key, default)
        
        response = client.post("/api/v1/payments/create-preference", json={"plan_type": "pro"})
        assert response.status_code == 200
        data = response.json()
        assert data["init_point"] == "http://mp.com/init"
        assert data["preference_id"] == "pref_123"

@patch("app.api.v1.payments.ensure_user", new_callable=AsyncMock)
@patch("app.api.v1.payments.register_payment", new_callable=AsyncMock)
@patch("app.api.v1.payments.httpx.AsyncClient")
def test_payment_success_security_check(mock_http, mock_register_payment, mock_ensure_user, client):
    mock_ensure_user.return_value = None
    mock_register_payment.return_value = None
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "approved",
        "metadata": {"plan_type": "pro", "user_email": "test@example.com"},
        "transaction_amount": 4990,
        "preference_id": "pref_123"
    }
    mock_response.raise_for_status = MagicMock()
    
    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_response
    mock_http.return_value.__aenter__.return_value = mock_client_instance

    with patch("fastapi.Request.session", new_callable=MagicMock) as mock_session:
        mock_session.get.side_effect = lambda key, default=None: {
            "user": {"email": "test@example.com", "name": "Test User"}
        }.get(key, default)
        
        response = client.get("/api/v1/payments/success?payment_id=pay_123&status=approved&preference_id=pref_123", follow_redirects=False)
        assert response.status_code == 307
        assert "payment=success" in response.headers["location"]
        mock_register_payment.assert_called_once()

@patch("app.api.v1.payments.ensure_user", new_callable=AsyncMock)
@patch("app.api.v1.payments.register_payment", new_callable=AsyncMock)
@patch("app.api.v1.payments.httpx.AsyncClient")
def test_payment_success_fraud_prevention(mock_http, mock_register_payment, mock_ensure_user, client):
    mock_ensure_user.return_value = None
    mock_register_payment.return_value = None
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "rejected",
        "metadata": {"plan_type": "pro", "user_email": "test@example.com"},
        "transaction_amount": 4990,
        "preference_id": "pref_123"
    }
    mock_response.raise_for_status = MagicMock()
    
    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_response
    mock_http.return_value.__aenter__.return_value = mock_client_instance

    with patch("fastapi.Request.session", new_callable=MagicMock) as mock_session:
        mock_session.get.side_effect = lambda key, default=None: {
            "user": {"email": "test@example.com", "name": "Test User"}
        }.get(key, default)
        
        response = client.get("/api/v1/payments/success?payment_id=pay_123&status=approved&preference_id=pref_123", follow_redirects=False)
        assert response.status_code == 307
        assert "payment=failure" in response.headers["location"]
        mock_register_payment.assert_not_called()

@patch("app.api.v1.payments.verify_webhook_signature")
@patch("app.api.v1.payments.ensure_user", new_callable=AsyncMock)
@patch("app.api.v1.payments.register_payment", new_callable=AsyncMock)
@patch("app.api.v1.payments.httpx.AsyncClient")
def test_webhook_payment_approved(mock_http, mock_register_payment, mock_ensure_user, mock_verify_sig, client):
    mock_verify_sig.return_value = True
    mock_ensure_user.return_value = None
    mock_register_payment.return_value = None
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "approved",
        "metadata": {"plan_type": "infinity", "user_email": "test@example.com"},
        "transaction_amount": 12990,
        "preference_id": "pref_123",
        "payer": {"email": "payer@example.com"}
    }
    
    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_response
    mock_http.return_value.__aenter__.return_value = mock_client_instance
    
    payload = {
        "type": "payment",
        "data": {"id": "1234567"}
    }
    
    response = client.post("/api/v1/payments/webhook", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_register_payment.assert_called_once()


import hmac
import hashlib
import time

@patch("app.api.v1.payments.ensure_user", new_callable=AsyncMock)
@patch("app.api.v1.payments.register_payment", new_callable=AsyncMock)
@patch("app.api.v1.payments.httpx.AsyncClient")
def test_webhook_signature_verification_success(mock_http, mock_register_payment, mock_ensure_user, client):
    mock_ensure_user.return_value = None
    mock_register_payment.return_value = None

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "approved",
        "metadata": {"plan_type": "infinity", "user_email": "test@example.com"},
        "transaction_amount": 12990,
        "preference_id": "pref_123",
        "payer": {"email": "payer@example.com"}
    }
    mock_client_instance = AsyncMock()
    mock_client_instance.get.return_value = mock_response
    mock_http.return_value.__aenter__.return_value = mock_client_instance

    secret = "test_secret"
    ts = str(int(time.time() * 1000))
    data_id = "1234567"
    x_request_id = "req-123"
    manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
    v1 = hmac.new(secret.encode(), msg=manifest.encode(), digestmod=hashlib.sha256).hexdigest()
    x_signature = f"ts={ts},v1={v1}"

    payload = {
        "type": "payment",
        "data": {"id": data_id}
    }

    with patch("app.api.v1.payments.MP_WEBHOOK_SECRET", secret):
        response = client.post(
            f"/api/v1/payments/webhook?data.id={data_id}",
            json=payload,
            headers={
                "x-signature": x_signature,
                "x-request-id": x_request_id
            }
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}


@patch("app.api.v1.payments.ensure_user", new_callable=AsyncMock)
@patch("app.api.v1.payments.register_payment", new_callable=AsyncMock)
@patch("app.api.v1.payments.httpx.AsyncClient")
def test_webhook_signature_verification_failure(mock_http, mock_register_payment, mock_ensure_user, client):
    mock_ensure_user.return_value = None
    mock_register_payment.return_value = None

    payload = {
        "type": "payment",
        "data": {"id": "1234567"}
    }

    response = client.post(
        "/api/v1/payments/webhook?data.id=1234567",
        json=payload,
        headers={
            "x-signature": "ts=123456,v1=invalid_hash",
            "x-request-id": "req-123"
        }
    )
    assert response.status_code == 400
    assert response.json() == {"error": "Firma inválida"}
