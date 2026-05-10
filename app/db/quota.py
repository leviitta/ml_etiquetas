"""
quota.py — Lógica de cuotas por usuario para PostgreSQL (asyncpg).
"""
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.db.database import get_db

FREE_DAILY_QUOTA   = int(os.getenv("FREE_DAILY_QUOTA",   "5"))
FREE_MONTHLY_QUOTA = int(os.getenv("FREE_MONTHLY_QUOTA", "20"))
PAID_MONTHLY_QUOTA = int(os.getenv("PAID_MONTHLY_QUOTA", "100"))  # docs extra por pago

async def ensure_user(email: str, name: str = ""):
    """Inserta el usuario si no existe."""
    async with get_db() as db:
        await db.execute(
            "INSERT INTO users (email, name) VALUES ($1, $2) ON CONFLICT (email) DO NOTHING",
            email, name
        )

async def get_quota_status(email: str) -> dict:
    """Retorna el estado de cuota del usuario."""
    # Usar Timezone de Chile para los límites diarios
    chile_tz = ZoneInfo("America/Santiago")
    now = datetime.now(timezone.utc)
    now_chile = now.astimezone(chile_tz)
    today_date = now_chile.date()

    async with get_db() as db:
        # Usos del día (calculado usando la medianoche de Chile)
        used_today = await db.fetchval(
            "SELECT COUNT(*) FROM quota_usage WHERE email = $1 AND DATE(used_at AT TIME ZONE 'America/Santiago') = $2",
            email, today_date
        )

        # Pagos activos aprobados y vigentes
        payments = await db.fetch(
            "SELECT valid_until, plan_type, created_at FROM payments "
            "WHERE email = $1 AND status = 'approved' AND valid_until >= $2",
            email, now.isoformat()
        )
        
        has_active_payment = len(payments) > 0
        pro_count = 0
        infinity_active = False
        latest_valid_until = None
        oldest_active_payment_date = None
        
        for p in payments:
            if latest_valid_until is None or p["valid_until"] > latest_valid_until:
                latest_valid_until = p["valid_until"]
                
            if oldest_active_payment_date is None or p["created_at"] < oldest_active_payment_date:
                oldest_active_payment_date = p["created_at"]
            
            plan = p["plan_type"] if "plan_type" in dict(p) else "pro"
            
            if plan == "infinity":
                infinity_active = True
            else:
                pro_count += 1

        payment_valid_until = latest_valid_until
        active_plan_type = "infinity" if infinity_active else ("pro" if pro_count > 0 else "starter")

        # --- CÁLCULO DEL CICLO ("MES") ---
        if has_active_payment and oldest_active_payment_date:
            oldest_chile = oldest_active_payment_date.astimezone(chile_tz)
            cycle_start_ts = datetime.combine(oldest_chile.date(), datetime.min.time(), tzinfo=chile_tz)
        else:
            first_use = await db.fetchval(
                "SELECT MIN(used_at) FROM quota_usage WHERE email = $1",
                email
            )
            
            if first_use:
                first_use_dt = first_use
                if first_use_dt.tzinfo is None:
                    first_use_dt = first_use_dt.replace(tzinfo=timezone.utc)
                
                days_since_first_use = (now - first_use_dt).days
                cycles_passed = days_since_first_use // 30
                
                from datetime import timedelta
                cycle_start_ts = first_use_dt + timedelta(days=cycles_passed * 30)
            else:
                cycle_start_ts = now

        # Usos del ciclo actual ("mes" dinámico)
        used_month = await db.fetchval(
            "SELECT COUNT(*) FROM quota_usage WHERE email = $1 AND used_at >= $2",
            email, cycle_start_ts
        )

    # Lógica de cuotas según plan
    if active_plan_type == "infinity":
        monthly_limit = 999999
        daily_limit   = 999999
    else:
        monthly_limit = FREE_MONTHLY_QUOTA + (PAID_MONTHLY_QUOTA * pro_count)
        daily_limit   = FREE_DAILY_QUOTA if active_plan_type == "starter" else 999999

    can_upload = True
    reason = None

    if used_today >= daily_limit:
        can_upload = False
        reason = "daily"
    elif used_month >= monthly_limit:
        can_upload = False
        reason = "monthly"

    return {
        "used_today":           used_today,
        "used_month":           used_month,
        "daily_limit":          daily_limit,
        "monthly_limit":        monthly_limit,
        "has_active_payment":   has_active_payment,
        "payment_valid_until":  payment_valid_until,
        "active_plan_type":     active_plan_type,
        "can_upload":           can_upload,
        "reason":               reason,
    }


class QuotaExceededException(Exception):
    def __init__(self, reason: str, detail: str, quota_status: dict):
        self.reason = reason
        self.detail = detail
        self.quota_status = quota_status
        super().__init__(detail)


async def verify_quota_for_batch(email: str, num_files: int):
    quota = await get_quota_status(email)

    if not quota["can_upload"]:
        raise QuotaExceededException(
            reason=quota["reason"],
            detail="Ya has alcanzado el límite de tu cuota.",
            quota_status=quota
        )

    remaining_today = quota["daily_limit"] - quota["used_today"]
    if num_files > remaining_today:
        raise QuotaExceededException(
            reason="daily",
            detail=f"Solo te quedan {remaining_today} etiqueta(s) disponibles hoy. Estás intentando subir {num_files}.",
            quota_status=quota
        )

    remaining_month = quota["monthly_limit"] - quota["used_month"]
    if num_files > remaining_month:
        raise QuotaExceededException(
            reason="monthly",
            detail=f"Solo te quedan {remaining_month} etiqueta(s) disponibles este mes. Estás intentando subir {num_files}.",
            quota_status=quota
        )


async def register_usage(email: str):
    async with get_db() as db:
        await db.execute("INSERT INTO quota_usage (email) VALUES ($1)", email)


async def register_payment(
    email: str,
    mp_payment_id: str,
    mp_preference_id: str,
    amount: float,
    valid_until: str,
    status: str = "approved",
    plan_type: str = "pro",
):
    async with get_db() as db:
        await db.execute(
            """INSERT INTO payments
               (email, mp_payment_id, mp_preference_id, amount, status, valid_until, plan_type)
               VALUES ($1, $2, $3, $4, $5, $6, $7)
               ON CONFLICT(mp_payment_id) DO UPDATE SET status = excluded.status, plan_type = excluded.plan_type
            """,
            email, mp_payment_id, mp_preference_id, amount, status, valid_until, plan_type
        )
