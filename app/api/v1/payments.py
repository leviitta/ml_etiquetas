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
import hmac
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.db.quota import ensure_user, register_payment, get_quota_status

logger = logging.getLogger(__name__)
router = APIRouter()

MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")
MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")
PAYMENT_PRO_AMOUNT = float(os.getenv("PAYMENT_PRO_AMOUNT", "4990"))
PAYMENT_INFINITY_AMOUNT = float(os.getenv("PAYMENT_INFINITY_AMOUNT", "12990"))
PAYMENT_UPGRADE_AMOUNT = float(os.getenv("PAYMENT_UPGRADE_AMOUNT", "8000"))
PAYMENT_DAYS    = int(os.getenv("PAYMENT_DAYS", "30"))
BASE_URL        = os.getenv("BASE_URL", "http://localhost:8000")

MP_BASE_URL = "https://api.mercadopago.com"


def _headers() -> dict[str, str]:
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
    
    target_plan = body.get("plan_type", "pro")
    email = user.get("email")

    current_plan = "starter"
    quota_status = await get_quota_status(email)
    if quota_status:
        current_plan = quota_status.get("active_plan_type", "starter")

    plan_desc = f"Acceso extendido por {PAYMENT_DAYS} días"

    if target_plan == "infinity":
        if current_plan == "pro":
            # Upgrading from Pro to Infinity
            plan_title = "Upgrade a Plan Infinity - MeliOps"
            final_amount = PAYMENT_UPGRADE_AMOUNT
        else:
            plan_title = "Plan Infinity - MeliOps"
            final_amount = PAYMENT_INFINITY_AMOUNT
    else:
        # For simplicity, if not Infinity, default to Pro
        target_plan = "pro" # Fallback por seguridad
        final_amount = PAYMENT_PRO_AMOUNT
        plan_title = "Plan Pro - MeliOps"

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
    session_email = user.get("email", "") if user else ""

    payment_id    = request.query_params.get("payment_id", "")
    preference_id = request.query_params.get("preference_id", "")
    status        = request.query_params.get("status", "unknown")

    if status == "approved":
        # Check plan type from preference metadata directly via MP API
        plan_type = "pro"
        final_amount = PAYMENT_PRO_AMOUNT
        email = session_email
        
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
                
                plan_type = payment_data.get("metadata", {}).get("plan_type", "pro")
                
                # Use session_email if present, else extract from payment data
                if not email:
                    email = payment_data.get("external_reference") or payment_data.get("metadata", {}).get("user_email") or payment_data.get("payer", {}).get("email", "")

                if not email:
                    logger.error("No se pudo identificar al usuario para el pago %s", payment_id)
                    return RedirectResponse(url="/api/v1/?payment=failure")
                
                # Check for actual payment status from API (security measure)
                if plan_type == "infinity":
                    fallback_amount = PAYMENT_INFINITY_AMOUNT
                else:
                    fallback_amount = PAYMENT_PRO_AMOUNT

                final_amount = float(payment_data.get("transaction_amount", fallback_amount))
            except Exception as e:
                logger.error("Error obteniendo metadata del pago en /success o pago falso: %s", e)
                return RedirectResponse(url="/api/v1/?payment=failure")
        else:
            # If there is no payment_id but status was "approved" in URL, it's likely a fraudulent direct request.
            logger.warning("Solicitud a /success sin payment_id pero con status approved.")
            return RedirectResponse(url="/api/v1/?payment=failure")

        valid_until = (datetime.now(timezone.utc) + timedelta(days=PAYMENT_DAYS)).isoformat()
        await ensure_user(email)
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


def verify_webhook_signature(request: Request, body_bytes: bytes) -> bool:
    """
    Verifica la firma HMAC-SHA256 de los webhooks de Mercado Pago.
    """
    if not MP_WEBHOOK_SECRET:
        logger.error("MP_WEBHOOK_SECRET no está configurado.")
        return False

    x_signature = request.headers.get("x-signature", "")
    x_request_id = request.headers.get("x-request-id", "")

    if not x_signature:
        logger.warning("Falta el encabezado x-signature.")
        return False

    # Parsear ts y v1 de x-signature
    parts = x_signature.split(",")
    ts = None
    v1 = None
    for part in parts:
        keyValue = part.split("=", 1)
        if len(keyValue) == 2:
            key = keyValue[0].strip()
            value = keyValue[1].strip()
            if key == "ts":
                ts = value
            elif key == "v1":
                v1 = value

    if not ts or not v1:
        logger.warning("Formato de x-signature inválido.")
        return False

    # Validar diferencia de timestamp (< 5 minutos)
    try:
        ts_val = int(ts)
        # Mercado Pago envía ts en milisegundos
        if ts_val > 1000000000000:
            ts_time = datetime.fromtimestamp(ts_val / 1000, tz=timezone.utc)
        else:
            ts_time = datetime.fromtimestamp(ts_val, tz=timezone.utc)
    except Exception as e:
        logger.warning("Error parseando timestamp: %s", e)
        return False

    now = datetime.now(timezone.utc)
    diff = abs((now - ts_time).total_seconds())
    if diff > 300:  # 5 minutos
        logger.warning("Timestamp del webhook expirado (diferencia de %s segundos).", diff)
        return False

    # Obtener data.id de query params o body
    data_id = request.query_params.get("data.id") or request.query_params.get("id")
    if not data_id:
        try:
            body = json.loads(body_bytes) if body_bytes else {}
            data_id = body.get("data", {}).get("id") or body.get("id")
        except Exception:
            pass

    data_id_str = str(data_id) if data_id is not None else ""

    # Construir manifest
    manifest_parts = []
    if data_id_str:
        manifest_parts.append(f"id:{data_id_str.lower()}")
    if x_request_id:
        manifest_parts.append(f"request-id:{x_request_id}")
    if ts:
        manifest_parts.append(f"ts:{ts}")

    manifest = ";".join(manifest_parts) + ";" if manifest_parts else ""

    # Calcular HMAC-SHA256
    try:
        hmac_obj = hmac.new(MP_WEBHOOK_SECRET.encode(), msg=manifest.encode(), digestmod=hashlib.sha256)
        sha = hmac_obj.hexdigest()
    except Exception as e:
        logger.error("Error calculando HMAC: %s", e)
        return False

    if not hmac.compare_digest(sha, v1):
        logger.warning("Firma de webhook inválida.")
        return False

    return True


# ── Webhook IPN ──────────────────────────────────────────────────────────────

@router.post("/webhook")
async def payment_webhook(request: Request):
    """
    Webhook IPN de Mercado Pago.
    Verifica el pago consultando la API REST y actualiza la base de datos.
    """
    body_bytes = await request.body()
    if not verify_webhook_signature(request, body_bytes):
        return JSONResponse(status_code=400, content={"error": "Firma inválida"})

    try:
        body = json.loads(body_bytes) if body_bytes else {}
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
    plan_type   = payment.get("metadata", {}).get("plan_type", "pro")
    pref_id     = payment.get("preference_id", "")

    if status == "approved" and user_email:
        valid_until = (datetime.now(timezone.utc) + timedelta(days=PAYMENT_DAYS)).isoformat()
        await ensure_user(user_email)
        
        if plan_type == "infinity":
            fallback_amount = PAYMENT_INFINITY_AMOUNT
        else:
            fallback_amount = PAYMENT_PRO_AMOUNT
            
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
