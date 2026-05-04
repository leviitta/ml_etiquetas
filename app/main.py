from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from app.api.v1.endpoints import router as extract_router
from app.api.v1.auth import router as auth_router
from app.api.v1.payments import router as payments_router
from app.db.database import init_db
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the database
    await init_db()
    yield
    # Shutdown logic (if any) could go here

app = FastAPI(
    title="Extractor de Etiquetas",
    description="API para extraer etiquetas de envío de MercadoLibre desde archivos PDF",
    version="1.0.0",
    lifespan=lifespan
)

# Add Session Middleware for OAuth
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "una_clave_secreta_de_respaldo"))

# Include the router for version 1 of our API
app.include_router(extract_router, prefix="/api/v1", tags=["etiquetas"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(payments_router, prefix="/api/v1/payments", tags=["payments"])

# Redirect root to our interface
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/api/v1/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)