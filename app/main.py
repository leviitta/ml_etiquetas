import os
import logging
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from app.api.v1.endpoints import router as extract_router
from app.api.v1.auth import router as auth_router
from app.api.v1.payments import router as payments_router
from app.db.database import init_db
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager

# Setup Google Cloud Logging if in GCP environment
if not os.getenv("TESTING"):
    try:
        import google.cloud.logging
        client = google.cloud.logging.Client()
        client.setup_logging()
        logging.info("Google Cloud Logging successfully configured.")
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        logging.info("Running locally or without GCP credentials, standard logging configured.")
else:
    logging.basicConfig(level=logging.INFO)
    logging.info("Running in testing mode, standard logging configured.")

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "https://www.meliops.cl", "https://meliops.cl"],
    allow_origin_regex=r"chrome-extension://[a-zA-Z0-9]+|https://.*\.mercadolibre\..*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Session Middleware for OAuth
secret_key = os.getenv("SECRET_KEY")
if not secret_key or secret_key == "una_clave_secreta_de_respaldo":
    raise RuntimeError("SECRET_KEY is missing or insecure")

app.add_middleware(
    SessionMiddleware,
    secret_key=secret_key,
    https_only=True,
    same_site="none"
)

class CustomStaticFiles(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

# Mount static files
app.mount("/static", CustomStaticFiles(directory="app/static"), name="static")

# Include the router for version 1 of our API
app.include_router(extract_router, prefix="/api/v1", tags=["etiquetas"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(payments_router, prefix="/api/v1/payments", tags=["payments"])

from app.api.root import router as root_router
app.include_router(root_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)