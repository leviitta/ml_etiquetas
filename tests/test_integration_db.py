import pytest
import os
from datetime import datetime, timezone, timedelta
from app.db.database import get_db
from app.db.quota import (
    ensure_user,
    get_quota_status,
    verify_quota_for_batch,
    register_usage,
    register_payment,
    QuotaExceededException,
)

# Skip all tests in this module if TESTING_WITH_REAL_DB is not set
pytestmark = pytest.mark.skipif(
    not os.getenv("TESTING_WITH_REAL_DB") in ("1", "true", "True"),
    reason="Requiere base de datos de pruebas real"
)

@pytest.mark.asyncio
async def test_ensure_user_integration():
    email = "test_integration@example.com"
    name = "Integration Test User"
    
    # Ensure user is created
    await ensure_user(email, name)
    
    # Verify directly in the database
    async with get_db() as db:
        row = await db.fetchrow("SELECT email, name FROM users WHERE email = $1", email)
        assert row is not None
        assert row["email"] == email
        assert row["name"] == name

@pytest.mark.asyncio
async def test_register_usage_and_quota_integration():
    email = "quota_test@example.com"
    await ensure_user(email, "Quota User")
    
    # Initial quota status
    status = await get_quota_status(email)
    assert status["used_today"] == 0
    assert status["used_month"] == 0
    assert status["can_upload"] is True
    
    # Register usage
    await register_usage(email)
    status = await get_quota_status(email)
    assert status["used_today"] == 1
    assert status["used_month"] == 1
    
    # Register up to the limit (FREE_DAILY_QUOTA is 5 by default)
    for _ in range(4):
        await register_usage(email)
        
    status = await get_quota_status(email)
    assert status["used_today"] == 5
    assert status["can_upload"] is False
    
    # Verify quota for batch should raise QuotaExceededException
    with pytest.raises(QuotaExceededException) as exc_info:
        await verify_quota_for_batch(email, 1)
    assert exc_info.value.reason == "daily"

@pytest.mark.asyncio
async def test_register_payment_integration():
    email = "payment_test@example.com"
    await ensure_user(email, "Payment User")
    
    # Register a payment for 'pro' plan valid for 30 days
    valid_until = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    await register_payment(
        email=email,
        mp_payment_id="pay_123456",
        mp_preference_id="pref_123456",
        amount=9990.0,
        valid_until=valid_until,
        status="approved",
        plan_type="pro"
    )
    
    # Verify quota status reflects the active payment and increased limits
    status = await get_quota_status(email)
    assert status["has_active_payment"] is True
    assert status["active_plan_type"] == "pro"
    # Daily limit for pro is unlimited (999999)
    assert status["daily_limit"] == 999999
    # Monthly limit is FREE_MONTHLY_QUOTA (20) + PAID_MONTHLY_QUOTA (100) = 120
    assert status["monthly_limit"] == 120
