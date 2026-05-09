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

from app.db.quota import ensure_user, register_payment, get_quota_status

logger = logging.getLogger(__name__)
router = APIRouter()

MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")
PAYMENT_PREMIUM_AMOUNT = float(os.getenv("PAYMENT_PREMIUM_AMOUNT", "4990"))
PAYMENT_UNLIMITED_AMOUNT = float(os.getenv("PAYMENT_UNLIMITED_AMOUNT", "12990"))
PAYMENT_UPGRADE_AMOUNT = float(os.getenv("PAYMENT_UPGRADE_AMOUNT", "8000"))
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
    
    # Obtener el plan deseado y cuota actual
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    
    target_plan = body.get("plan_type", "premium")
    quota_status = await get_quota_status(email)
    current_plan = quota_status.get("active_plan_type", "free")
    
    # Definir precios según el plan
    if target_plan == "unlimited":
        if current_plan == "premium":
            final_amount = PAYMENT_UPGRADE_AMOUNT  # Pago de la diferencia
        else:
            final_amount = PAYMENT_UNLIMITED_AMOUNT
        plan_title = "Plan Sin Límites - MeliOps"
        plan_desc = f"Acceso ilimitado por {PAYMENT_DAYS} días"
    else:
        target_plan = "premium" # Fallback por seguridad
        final_amount = PAYMENT_PREMIUM_AMOUNT
        plan_title = "Plan Premium - MeliOps"
        plan_desc = f"Acceso extendido por {PAYMENT_DAYS} días"

    # auto_return y notification_url solo funcionan con URLs públicas (no localhost)
    is_public = BASE_URL.startswith("https://") and "localhost" not in BASE_URL

    # Separar nombre y apellido para Mercado Pago
    full_name = user.get("name", "")
    name_parts = full_name.split(" ", 1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    client_base_url = str(request.base_url).rstrip("/")

    preference_data = {
        "items": [
            {
                "id": "quota-mensual",
                "title": plan_title,
                "description": plan_desc,
                "category_id": "services",
                "quantity": 1,
                "currency_id": "CLP",
                "unit_price": final_amount,
            }
        ],
        "payer": {
            "email": email,
            "name": first_name,
            "surname": last_name
        },
        "back_urls": {
            "success": f"{client_base_url}/api/v1/payments/success",
            "failure": f"{client_base_url}/api/v1/payments/failure",
            "pending": f"{client_base_url}/api/v1/payments/pending",
        },
        "metadata": {"user_email": email, "plan_type": target_plan},
        "statement_descriptor": "ETIQUETAS ML",
        "external_reference": email,
        "binary_mode": True,
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
        # Check plan type from preference metadata directly via MP API
        plan_type = "premium"
        final_amount = PAYMENT_PREMIUM_AMOUNT
        if payment_id and MP_ACCESS_TOKEN:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{MP_BASE_URL}/v1/payments/{payment_id}",
                        headers=_headers(),
                        timeout=5,
                    )
                    resp.raise_for_status()  # Check for 404 or other errors
                
                payment_data = resp.json()
                
                # Check real status from API, not URL
                real_status = payment_data.get("status")
                if real_status != "approved":
                    logger.warning(f"Intento de fraude o pago no aprobado: {payment_id}")
                    return RedirectResponse(url="/api/v1/?payment=failure")
                
                plan_type = payment_data.get("metadata", {}).get("plan_type", "premium")
                
                # Assign final amount based on plan type fallback if not present in API call
                if plan_type == "unlimited":
                    fallback_amount = PAYMENT_UNLIMITED_AMOUNT
                else:
                    fallback_amount = PAYMENT_PREMIUM_AMOUNT

                final_amount = float(payment_data.get("transaction_amount", fallback_amount))
            except Exception as e:
                logger.error("Error obteniendo metadata del pago en /success o pago falso: %s", e)
                return RedirectResponse(url="/api/v1/?payment=failure")
        else:
            # If there is no payment_id but status was "approved" in URL, it's likely a fraudulent direct request.
            logger.warning("Solicitud a /success sin payment_id pero con status approved.")
            return RedirectResponse(url="/api/v1/?payment=failure")

        valid_until = (datetime.now(timezone.utc) + timedelta(days=PAYMENT_DAYS)).isoformat()
        await register_payment(
            email=email,
            mp_payment_id=payment_id,
            mp_preference_id=preference_id,
            amount=final_amount,
            valid_until=valid_until,
            status="approved",
            plan_type=plan_type,
        )
        logger.info("Pago aprobado para %s hasta %s con plan %s", email, valid_until, plan_type)

    return RedirectResponse(url="/api/v1/?payment=success")


@router.get("/failure")
async def payment_failure(request: Request):
    return RedirectResponse(url="/api/v1/?payment=failure")


@router.get("/pending")
async def payment_pending(request: Request):
    return RedirectResponse(url="/api/v1/?payment=pending")


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
    plan_type   = payment.get("metadata", {}).get("plan_type", "premium")
    pref_id     = payment.get("preference_id", "")

    if status == "approved" and user_email:
        valid_until = (datetime.now(timezone.utc) + timedelta(days=PAYMENT_DAYS)).isoformat()
        await ensure_user(user_email)
        
        if plan_type == "unlimited":
            fallback_amount = PAYMENT_UNLIMITED_AMOUNT
        else:
            fallback_amount = PAYMENT_PREMIUM_AMOUNT
            
        await register_payment(
            email=user_email,
            mp_payment_id=str(res_id),
            mp_preference_id=pref_id,
            amount=float(payment.get("transaction_amount", fallback_amount)),
            valid_until=valid_until,
            status="approved",
            plan_type=plan_type,
        )
        logger.info("Webhook: pago aprobado para %s con plan %s", user_email, plan_type)

    return JSONResponse(content={"ok": True})
