import pytest
from app.db.quota import verify_quota_for_batch, QuotaExceededException
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
@patch('app.db.quota.get_quota_status')
async def test_verify_quota_anon_no_quota(mock_get_quota):
    # Simulamos a un usuario anonimo sin cuota
    mock_get_quota.return_value = {
        "can_upload": False,
        "reason": "daily",
        "used_today": 5,
        "daily_limit": 5,
        "monthly_limit": 20,
        "used_month": 5
    }
    
    with pytest.raises(QuotaExceededException) as exc_info:
        await verify_quota_for_batch("anon_123456", 1)
        
    assert "Si compraste un plan, por favor inicia sesión." in exc_info.value.detail
    assert exc_info.value.reason == "daily"


@pytest.mark.asyncio
@patch('app.db.quota.get_quota_status')
async def test_verify_quota_logged_no_quota(mock_get_quota):
    # Simulamos a un usuario logueado sin cuota (no debe decirle que inicie sesión)
    mock_get_quota.return_value = {
        "can_upload": False,
        "reason": "daily",
        "used_today": 5,
        "daily_limit": 5,
        "monthly_limit": 20,
        "used_month": 5
    }
    
    with pytest.raises(QuotaExceededException) as exc_info:
        await verify_quota_for_batch("user@example.com", 1)
        
    assert "Si compraste un plan, por favor inicia sesión." not in exc_info.value.detail
    assert "Ya has alcanzado el límite" in exc_info.value.detail

@pytest.mark.asyncio
@patch('app.db.quota.get_quota_status')
async def test_verify_quota_anon_exceeds_batch(mock_get_quota):
    # Simulamos a un usuario anonimo que sube más de los permitidos en el batch
    mock_get_quota.return_value = {
        "can_upload": True,
        "reason": None,
        "used_today": 3,
        "daily_limit": 5,
        "monthly_limit": 20,
        "used_month": 3
    }
    
    with pytest.raises(QuotaExceededException) as exc_info:
        await verify_quota_for_batch("anon_123456", 5) # 3 + 5 > 5
        
    assert "Si compraste un plan, por favor inicia sesión." in exc_info.value.detail
    assert "Solo te quedan 2 etiqueta(s) disponibles hoy" in exc_info.value.detail

