"""
quota.py — Lógica de cuotas por usuario.
- FREE_DAILY_QUOTA: documentos gratuitos por día (env: FREE_DAILY_QUOTA, default 5)
- FREE_MONTHLY_QUOTA: documentos gratuitos por mes (env: FREE_MONTHLY_QUOTA, default 20)
- Un pago aprobado extiende la cuota mensual en +PAID_MONTHLY_QUOTA documentos extra.
"""
import os
import aiosqlite
from datetime import datetime, timezone
from app.db.database import get_db

FREE_DAILY_QUOTA   = int(os.getenv("FREE_DAILY_QUOTA",   "5"))
FREE_MONTHLY_QUOTA = int(os.getenv("FREE_MONTHLY_QUOTA", "20"))
PAID_MONTHLY_QUOTA = int(os.getenv("PAID_MONTHLY_QUOTA", "100"))  # docs extra por pago


async def ensure_user(email: str, name: str = ""):
    """Inserta el usuario si no existe."""
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (email, name) VALUES (?, ?)",
            (email, name),
        )
        await db.commit()


async def get_quota_status(email: str) -> dict:
    """
    Retorna el estado de cuota del usuario:
    {
        used_today: int,
        used_month: int,
        daily_limit: int,
        monthly_limit: int,
        has_active_payment: bool,
        payment_valid_until: str | None,
        can_upload: bool,
        reason: str | None,
    }
    """
    now = datetime.now(timezone.utc)
    today_str  = now.strftime("%Y-%m-%d")
    month_str  = now.strftime("%Y-%m")

    async with get_db() as db:
        db.row_factory = aiosqlite.Row

        # Usos del día
        row = await db.execute(
            "SELECT COUNT(*) as cnt FROM quota_usage "
            "WHERE email = ? AND date(used_at) = date(?)",
            (email, today_str),
        )
        used_today = (await row.fetchone())["cnt"]

        # Usos del mes
        row = await db.execute(
            "SELECT COUNT(*) as cnt FROM quota_usage "
            "WHERE email = ? AND strftime('%Y-%m', used_at) = ?",
            (email, month_str),
        )
        used_month = (await row.fetchone())["cnt"]

        # Pagos activos aprobados y vigentes
        row = await db.execute(
            "SELECT valid_until FROM payments "
            "WHERE email = ? AND status = 'approved' AND datetime(valid_until) >= datetime(?)"
            "ORDER BY valid_until DESC LIMIT 1",
            (email, now.isoformat()),
        )
        payment_row = await row.fetchone()
        has_active_payment = payment_row is not None
        payment_valid_until = payment_row["valid_until"] if payment_row else None

    monthly_limit = FREE_MONTHLY_QUOTA + (PAID_MONTHLY_QUOTA if has_active_payment else 0)
    daily_limit   = FREE_DAILY_QUOTA if not has_active_payment else monthly_limit

    # Evaluar si puede subir
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
    """
    Verifica si el lote de archivos a procesar excede la cuota del usuario.
    Lanza QuotaExceededException si se excede el límite.
    """
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
            detail=f"Solo te quedan {remaining_today} documento(s) disponibles hoy. Estás intentando subir {num_files}.",
            quota_status=quota
        )

    remaining_month = quota["monthly_limit"] - quota["used_month"]
    if num_files > remaining_month:
        raise QuotaExceededException(
            reason="monthly",
            detail=f"Solo te quedan {remaining_month} documento(s) disponibles este mes. Estás intentando subir {num_files}.",
            quota_status=quota
        )


async def register_usage(email: str):
    """Registra un documento procesado para el usuario."""
    async with get_db() as db:
        await db.execute(
            "INSERT INTO quota_usage (email) VALUES (?)", (email,)
        )
        await db.commit()


async def register_payment(
    email: str,
    mp_payment_id: str,
    mp_preference_id: str,
    amount: float,
    valid_until: str,
    status: str = "approved",
):
    """Guarda o actualiza un pago en la base de datos."""
    async with get_db() as db:
        await db.execute(
            """INSERT INTO payments
               (email, mp_payment_id, mp_preference_id, amount, status, valid_until)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(mp_payment_id) DO UPDATE SET status = excluded.status
            """,
            (email, mp_payment_id, mp_preference_id, amount, status, valid_until),
        )
        await db.commit()
