from typing import Dict, Any
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from app.db.quota import register_usage

router = APIRouter()

@router.post("/quota/register")
async def register_quota_usage(request: Request, payload: Dict[str, Any]):
    """Registra el uso de cuota en la base de datos cuando se descarga la etiqueta"""
    user = request.session.get('user')
    if user and user.get("email"):
        identifier = user["email"]
    else:
        identifier = request.session.get("anon_id")
        if not identifier:
            return JSONResponse(status_code=400, content={"error": "Sesión inválida."})
            
    count = payload.get("count", 1)
    for _ in range(count):
        await register_usage(identifier)
        
    return JSONResponse(content={"success": True})
