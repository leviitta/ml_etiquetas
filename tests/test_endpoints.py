import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import UploadFile
from app.db.quota import QuotaExceededException

@patch("app.api.v1.router_ui.ensure_user", new_callable=AsyncMock)
@patch("app.api.v1.router_ui.get_quota_status", new_callable=AsyncMock)
def test_get_index_anonymous(mock_get_quota, mock_ensure_user, client):
    mock_get_quota.return_value = {
        "can_upload": True,
        "reason": None,
        "used_today": 0,
        "daily_limit": 5,
        "monthly_limit": 20,
        "used_month": 0,
        "active_plan_type": "starter"
    }
    
    response = client.get("/")
    assert response.status_code == 200
    assert "MeliOps" in response.text
    assert "Optimizador de Etiquetas" in response.text
    mock_ensure_user.assert_called_once()
    mock_get_quota.assert_called_once()


@patch("app.api.v1.router_ui.ensure_user", new_callable=AsyncMock)
@patch("app.api.v1.router_ui.get_quota_status", new_callable=AsyncMock)
def test_get_index_logged_in(mock_get_quota, mock_ensure_user, client):
    mock_get_quota.return_value = {
        "can_upload": True,
        "reason": None,
        "used_today": 2,
        "daily_limit": 5,
        "monthly_limit": 20,
        "used_month": 2,
        "active_plan_type": "starter"
    }
    
    with patch("fastapi.Request.session", new_callable=MagicMock) as mock_session:
        mock_session.get.side_effect = lambda key, default=None: {
            "user": {"email": "test@example.com", "name": "Test User"}
        }.get(key, default)
        
        response = client.get("/")
        assert response.status_code == 200
        assert "MeliOps" in response.text


def test_get_faq(client):
    response = client.get("/faq")
    assert response.status_code == 200
    assert "Cómo Separar Etiquetas de Mercado Libre" in response.text


def test_extract_no_files(client):
    response = client.post("/api/v1/extract", files={})
    assert response.status_code in (400, 422)


@patch("app.api.v1.router_extract.ensure_user", new_callable=AsyncMock)
def test_extract_file_too_large(mock_ensure_user, client):
    large_content = b"%PDF-1.4 " + b"x" * (2000 * 1024 + 1)
    files = [("files", ("large.pdf", large_content, "application/pdf"))]
    response = client.post("/api/v1/extract", files=files)
    assert response.status_code == 400
    assert "supera el límite de tamaño" in response.json()["error"]
    assert "2 MB" in response.json()["error"]


@patch("app.api.v1.router_extract.ensure_user", new_callable=AsyncMock)
@patch("app.api.v1.router_extract.verify_quota_for_batch", new_callable=AsyncMock)
def test_extract_quota_exceeded(mock_verify_quota, mock_ensure_user, client):
    mock_verify_quota.side_effect = QuotaExceededException(reason="daily", detail="Quota exceeded detail", quota_status={})
    
    files = [("files", ("test.pdf", b"%PDF-1.4 dummy content", "application/pdf"))]
    response = client.post("/api/v1/extract", files=files)
    
    assert response.status_code == 403
    assert "error" in response.json()
    assert "Quota exceeded detail" in response.json()["error"]


@patch("app.api.v1.router_extract.ensure_user", new_callable=AsyncMock)
@patch("app.api.v1.router_extract.verify_quota_for_batch", new_callable=AsyncMock)
@patch("app.api.v1.router_extract.process_multiple_labels")
def test_extract_success(mock_process, mock_verify_quota, mock_ensure_user, client):
    mock_verify_quota.return_value = None
    mock_process.return_value = "dummy_output.pdf"
    
    def side_effect_process(input_paths, output_path):
        with open(output_path, "wb") as f:
            f.write(b"%PDF-1.4 mock output pdf")
        return output_path
        
    mock_process.side_effect = side_effect_process
    
    files = [("files", ("test.pdf", b"%PDF-1.4 dummy input content", "application/pdf"))]
    response = client.post("/api/v1/extract", files=files)
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.4 mock output pdf"
    mock_verify_quota.assert_called_once()
    mock_process.assert_called_once()


def test_secret_key_validation():
    import os
    import sys
    import importlib
    import pytest
    
    orig_secret = os.environ.get("SECRET_KEY")
    original_getenv = os.getenv
    
    def mock_getenv_none(key, default=None):
        if key == "SECRET_KEY":
            return None
        return original_getenv(key, default)
        
    def mock_getenv_insecure(key, default=None):
        if key == "SECRET_KEY":
            return "una_clave_secreta_de_respaldo"
        return original_getenv(key, default)
    
    try:
        with patch("os.getenv", side_effect=mock_getenv_none):
            with pytest.raises(RuntimeError, match="SECRET_KEY is missing or insecure"):
                if "app.main" in sys.modules:
                    importlib.reload(sys.modules["app.main"])
                else:
                    import app.main
                
        with patch("os.getenv", side_effect=mock_getenv_insecure):
            with pytest.raises(RuntimeError, match="SECRET_KEY is missing or insecure"):
                if "app.main" in sys.modules:
                    importlib.reload(sys.modules["app.main"])
                else:
                    import app.main
    finally:
        if orig_secret is not None:
            os.environ["SECRET_KEY"] = orig_secret
        if "app.main" in sys.modules:
            try:
                importlib.reload(sys.modules["app.main"])
            except Exception:
                pass


def test_cors_headers(client):
    response = client.options(
        "/api/v1/extract",
        headers={
            "Origin": "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "chrome-extension://abcdefghijklmnopqrstuvwxyzabcdef"
    assert response.headers.get("access-control-allow-credentials") == "true"


