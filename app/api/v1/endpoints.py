from fastapi import APIRouter
from app.api.v1.router_ui import router as ui_router
from app.api.v1.router_extract import router as extract_router
from app.api.v1.router_quota import router as quota_router

router = APIRouter()

# Registrar los submódulos modulares en el router v1 principal
router.include_router(ui_router)
router.include_router(extract_router)
router.include_router(quota_router)
