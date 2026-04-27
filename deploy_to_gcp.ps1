# Script de Despliegue Automatizado para GCP (Google Cloud Platform)
# Ejecuta este script desde la terminal de Windows PowerShell

# ── Configuración del proyecto ──────────────────────────────────────────────
$PROJECT_ID  = "ml-etiquetas"
$REGION      = "us-central1"
$REPO        = "ml-etiquetas-repo"
$SERVICE     = "ml-etiquetas-service"
$IMAGE       = "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/app:latest"
$SERVICE_URL = "https://$SERVICE-890639424998.$REGION.run.app"
# ────────────────────────────────────────────────────────────────────────────

# ── Variables de entorno (leídas del .env local) ────────────────────────────
if (-not (Test-Path .env)) {
    Write-Host "❌ No se encontró el archivo .env. Es necesario para configurar OAuth." -ForegroundColor Red
    exit 1
}

$envVars = @{}
Get-Content .env | Where-Object { $_ -match "^\s*[^#].*=.*" } | ForEach-Object {
    $parts = $_ -split "=", 2
    $envVars[$parts[0].Trim()] = $parts[1].Trim()
}

$GOOGLE_CLIENT_ID     = $envVars["GOOGLE_CLIENT_ID"]
$GOOGLE_CLIENT_SECRET = $envVars["GOOGLE_CLIENT_SECRET"]
$SECRET_KEY           = $envVars["SECRET_KEY"]
# En producción la REDIRECT_URI apunta a Cloud Run, no a localhost
$REDIRECT_URI         = "$SERVICE_URL/api/v1/auth/callback"
# ────────────────────────────────────────────────────────────────────────────

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "🚀 Iniciando despliegue de ML Etiquetas a GCP" -ForegroundColor Cyan
Write-Host "   Proyecto     : $PROJECT_ID"                 -ForegroundColor Cyan
Write-Host "   Imagen        : $IMAGE"                     -ForegroundColor Cyan
Write-Host "   Redirect URI  : $REDIRECT_URI"              -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# 1. Construir e subir la imagen mediante Cloud Build (que usa cloudbuild.yaml)
Write-Host "[1/2] Construyendo y subiendo la imagen a Artifact Registry..." -ForegroundColor Yellow
gcloud builds submit --config cloudbuild.yaml --project $PROJECT_ID .

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error al construir o subir la imagen. Abortando el despliegue." -ForegroundColor Red
    exit 1
}

Write-Host "✅ Imagen construida exitosamente." -ForegroundColor Green
Write-Host ""

# 2. Desplegar en Cloud Run con variables de entorno
Write-Host "[2/2] Desplegando el contenedor en Google Cloud Run..." -ForegroundColor Yellow
gcloud run deploy $SERVICE `
    --image $IMAGE `
    --region $REGION `
    --platform managed `
    --port 8080 `
    --allow-unauthenticated `
    --memory 2Gi `
    --set-env-vars "GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID,GOOGLE_CLIENT_SECRET=$GOOGLE_CLIENT_SECRET,SECRET_KEY=$SECRET_KEY,REDIRECT_URI=$REDIRECT_URI" `
    --project $PROJECT_ID

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error al desplegar en Cloud Run." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "🎉 Despliegue completado exitosamente." -ForegroundColor Green
Write-Host "   URL del servicio: $SERVICE_URL"            -ForegroundColor Green
Write-Host "   Redirect URI configurada: $REDIRECT_URI"  -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Host "⚠️  IMPORTANTE: Añade esta URI en Google Cloud Console:" -ForegroundColor Yellow
Write-Host "   $REDIRECT_URI" -ForegroundColor Yellow
Write-Host "   APIs y Servicios → Credenciales → tu OAuth Client ID → Authorized redirect URIs" -ForegroundColor DarkGray
