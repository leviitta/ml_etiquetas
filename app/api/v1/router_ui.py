import os
import uuid
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.db.quota import get_quota_status, ensure_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

def format_price(amount: float) -> str:
    """Format price to a string like 4.990"""
    return f"{int(amount):,}".replace(",", ".")

@router.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """Render the upload form"""
    user = request.session.get('user')
    
    # 1. Identificar al usuario (Logueado o Anónimo)
    if user and user.get("email"):
        identifier = user["email"]
    else:
        # Generar ID anónimo si no existe
        if not request.session.get("anon_id"):
            request.session["anon_id"] = f"anon_{uuid.uuid4().hex[:12]}"
        identifier = request.session["anon_id"]

    # 2. Registrar el usuario en la BD (como email o anon_id) para que funcione quota_usage
    await ensure_user(identifier, user.get("name", "Usuario Anónimo") if user else "Usuario Anónimo")
    
    quota_status = await get_quota_status(identifier)
        
    prices = {
        "pro": format_price(float(os.getenv("PAYMENT_PRO_AMOUNT", "4990"))),
        "infinity": format_price(float(os.getenv("PAYMENT_INFINITY_AMOUNT", "12990"))),
        "upgrade": format_price(float(os.getenv("PAYMENT_UPGRADE_AMOUNT", "8000")))
    }
        
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={"user": user, "quota_status": quota_status, "prices": prices}
    )

@router.get("/faq", response_class=HTMLResponse)
async def get_faq(request: Request):
    """Render the FAQ page"""
    user = request.session.get('user')
    return templates.TemplateResponse(
        request=request, 
        name="faq.html", 
        context={"user": user}
    )
