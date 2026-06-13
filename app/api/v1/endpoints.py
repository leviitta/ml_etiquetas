from fastapi import APIRouter
from app.api.v1.router_extract import router as extract_router
from app.api.v1.router_quota import router as quota_router

router = APIRouter()

# Registrar los submódulos de la API v1 (interfaz máquina-a-máquina)
router.include_router(extract_router, tags=["etiquetas"])
router.include_router(quota_router, tags=["quota"])
