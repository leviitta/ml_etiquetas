"""
payments.py — Router de Mercado Pago (usando httpx directo, sin SDK).
Endpoints:
  POST /api/v1/payments/create-preference  → Crea preferencia de pago MP
  GET  /api/v1/payments/success             → Redirección tras pago aprobado
  GET  /api/v1/payments/failure             → Redirección tras pago fallido
  GET  /api/v1/payments/pending             → Redirección tras pago pendiente
  POST /api/v1/payments/webhook             → IPN/Webhook de Mercado Pago
"""
import os
import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.db.quota import ensure_user, register_payment

logger = logging.getLogger(__name__)
router = APIRouter()

MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")
PAYMENT_AMOUNT  = float(os.getenv("PAYMENT_AMOUNT", "4990"))
PAYMENT_DAYS    = int(os.getenv("PAYMENT_DAYS", "30"))
BASE_URL        = os.getenv("BASE_URL", "http://localhost:8000")

MP_BASE_URL = "https://api.mercadopago.com"


def _headers() -> dict:
    if not MP_ACCESS_TOKEN:
        raise RuntimeError("MP_ACCESS_TOKEN no está configurado en .env")
    return {
        "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


# ── Crear preferencia de pago ────────────────────────────────────────────────

@router.post("/create-preference")
async def create_preference(request: Request):
    """Crea una preferencia de pago en Mercado Pago y devuelve el init_point."""
    user = request.session.get("user")
    if not user:
        return JSONResponse(status_code=401, content={"error": "Debes iniciar sesión."})

    email = user.get("email", "")
    await ensure_user(email, user.get("name", ""))

    # auto_return y notification_url solo funcionan con URLs públicas (no localhost)
    is_public = BASE_URL.startswith("https://") and "localhost" not in BASE_URL

    preference_data = {
        "items": [
            {
                "id": "quota-mensual",
                "title": "Cuota mensual – Optimizador Etiquetas ML",
                "description": f"Acceso extendido por {PAYMENT_DAYS} días",
                "quantity": 1,
                "currency_id": "CLP",
                "unit_price": PAYMENT_AMOUNT,
            }
        ],
        "payer": {"email": email},
        "back_urls": {
            "success": f"{BASE_URL}/api/v1/payments/success",
            "failure": f"{BASE_URL}/api/v1/payments/failure",
            "pending": f"{BASE_URL}/api/v1/payments/pending",
        },
        "metadata": {"user_email": email},
        "statement_descriptor": "ETIQUETAS ML",
    }

    # auto_return requiere back_urls públicas con HTTPS
    if is_public:
        preference_data["auto_return"] = "approved"
        preference_data["notification_url"] = f"{BASE_URL}/api/v1/payments/webhook"


    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{MP_BASE_URL}/checkout/preferences",
                headers=_headers(),
                json=preference_data,
                timeout=15,
            )
    except Exception as e:
        logger.error("Error conectando con Mercado Pago: %s", e)
        return JSONResponse(status_code=502, content={"error": "No se pudo conectar con Mercado Pago."})

    if resp.status_code not in (200, 201):
        logger.error("Error creando preferencia MP [%s]: %s", resp.status_code, resp.text)
        return JSONResponse(status_code=500, content={"error": "No se pudo crear la preferencia de pago."})

    data = resp.json()
    return JSONResponse(
        content={
            "init_point":         data["init_point"],
            "sandbox_init_point": data.get("sandbox_init_point", ""),
            "preference_id":      data["id"],
        }
    )


# ── Callbacks de redirección ─────────────────────────────────────────────────

@router.get("/success")
async def payment_success(request: Request):
    """
    Mercado Pago redirige aquí con ?payment_id=...&status=approved&...
    Registramos el pago y redirigimos al home.
    """
    user  = request.session.get("user")
    email = user.get("email", "") if user else ""

    payment_id    = request.query_params.get("payment_id", "")
    preference_id = request.query_params.get("preference_id", "")
    status        = request.query_params.get("status", "unknown")

    if email and status == "approved":
        valid_until = (datetime.now(timezone.utc) + timedelta(days=PAYMENT_DAYS)).isoformat()
        await register_payment(
            email=email,
            mp_payment_id=payment_id,
            mp_preference_id=preference_id,
            amount=PAYMENT_AMOUNT,
            valid_until=valid_until,
            status="approved",
        )
        logger.info("Pago aprobado para %s hasta %s", email, valid_until)

    return RedirectResponse(url="/?payment=success")


@router.get("/failure")
async def payment_failure(request: Request):
    return RedirectResponse(url="/?payment=failure")


@router.get("/pending")
async def payment_pending(request: Request):
    return RedirectResponse(url="/?payment=pending")


# ── Webhook IPN ──────────────────────────────────────────────────────────────

@router.post("/webhook")
async def payment_webhook(request: Request):
    """
    Webhook IPN de Mercado Pago.
    Verifica el pago consultando la API REST y actualiza la base de datos.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    topic  = body.get("type") or request.query_params.get("topic", "")
    res_id = body.get("data", {}).get("id") or request.query_params.get("id", "")

    if topic not in ("payment", "merchant_order") or not res_id or not MP_ACCESS_TOKEN:
        return JSONResponse(content={"ok": True})

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{MP_BASE_URL}/v1/payments/{res_id}",
                headers=_headers(),
                timeout=15,
            )
        payment = resp.json()
    except Exception as e:
        logger.error("Error consultando pago %s: %s", res_id, e)
        return JSONResponse(content={"ok": True})

    status      = payment.get("status", "")
    payer_email = payment.get("payer", {}).get("email", "")
    user_email  = payment.get("metadata", {}).get("user_email", payer_email)
    pref_id     = payment.get("preference_id", "")

    if status == "approved" and user_email:
        valid_until = (datetime.now(timezone.utc) + timedelta(days=PAYMENT_DAYS)).isoformat()
        await ensure_user(user_email)
        await register_payment(
            email=user_email,
            mp_payment_id=str(res_id),
            mp_preference_id=pref_id,
            amount=float(payment.get("transaction_amount", PAYMENT_AMOUNT)),
            valid_until=valid_until,
            status="approved",
        )
        logger.info("Webhook: pago aprobado para %s", user_email)

    return JSONResponse(content={"ok": True})
