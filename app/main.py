import os
import logging
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.api.v1.endpoints import router as extract_router
from app.api.v1.auth import router as auth_router
from app.api.v1.payments import router as payments_router
from app.db.database import init_db
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager

# Setup Google Cloud Logging if in GCP environment
try:
    import google.cloud.logging
    client = google.cloud.logging.Client()
    client.setup_logging()
    logging.info("Google Cloud Logging successfully configured.")
except Exception as e:
    logging.basicConfig(level=logging.INFO)
    logging.info("Running locally or without GCP credentials, standard logging configured.")

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

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include the router for version 1 of our API
app.include_router(extract_router, prefix="/api/v1", tags=["etiquetas"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(payments_router, prefix="/api/v1/payments", tags=["payments"])

from fastapi.responses import PlainTextResponse

@app.get("/robots.txt", include_in_schema=False, response_class=PlainTextResponse)
async def robots_txt():
    return "User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: https://meliops.app/sitemap.xml"

@app.get("/sitemap.xml", include_in_schema=False, response_class=PlainTextResponse)
async def sitemap_xml():
    return """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://meliops.app/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>"""

# Redirect root to our interface
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/api/v1/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)