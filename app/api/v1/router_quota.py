from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from app.db.quota import register_usage

router = APIRouter()


class QuotaRegisterPayload(BaseModel):
    count: int = Field(default=1, ge=1)


@router.post("/quota/register")
async def register_quota_usage(request: Request, payload: QuotaRegisterPayload):
    """Registra el uso de cuota en la base de datos cuando se descarga la etiqueta"""
    user = request.session.get('user')
    if user and user.get("email"):
        identifier = user["email"]
    else:
        identifier = request.session.get("anon_id")
        if not identifier:
            raise HTTPException(status_code=400, detail="Sesión inválida.")

    for _ in range(payload.count):
        await register_usage(identifier)

    return {"success": True}
