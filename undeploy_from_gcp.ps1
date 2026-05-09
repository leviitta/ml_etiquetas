# Script para Bajar la Aplicación de GCP (Google Cloud Platform)
# Ejecuta este script desde la terminal de Windows PowerShell

# ── Variables de entorno (leídas del .env local) ────────────────────────────
if (-not (Test-Path .env)) {
    Write-Host "❌ No se encontró el archivo .env." -ForegroundColor Red
    exit 1
}

$envVars = @{}
Get-Content .env | Where-Object { $_ -match "^\s*[^#].*=.*" } | ForEach-Object {
    $parts = $_ -split "=", 2
    $envVars[$parts[0].Trim()] = $parts[1].Trim()
}

$PROJECT_ID         = $envVars["GCP_PROJECT_ID"]
$REGION             = $envVars["GCP_REGION"]
$SERVICE            = $envVars["GCP_SERVICE"]
$SERVICE_ACCOUNT    = $envVars["GCP_SERVICE_ACCOUNT"]
$CUSTOM_DOMAIN      = $envVars["CUSTOM_DOMAIN"]

if (-not $PROJECT_ID -or -not $REGION -or -not $SERVICE) {
    Write-Host "❌ Faltan variables de GCP en el archivo .env." -ForegroundColor Red
    exit 1
}
$SA_EMAIL = "$SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com"

# ────────────────────────────────────────────────────────────────────────────

Write-Host "=============================================" -ForegroundColor Red
Write-Host "⚠️ Iniciando proceso para dar de baja ML Etiquetas de GCP" -ForegroundColor Red
Write-Host "   Proyecto : $PROJECT_ID" -ForegroundColor Red
Write-Host "   Servicio : $SERVICE"   -ForegroundColor Red
Write-Host "=============================================" -ForegroundColor Red
Write-Host ""

$confirmation = Read-Host "Esto eliminará el servicio '$SERVICE' de Cloud Run impidiendo su acceso en la web. ¿Estás seguro? (S/N)"
if ($confirmation -notmatch "^[sS]") {
    Write-Host "Operación cancelada por el usuario." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "[1/4] Eliminando el servicio de Google Cloud Run..." -ForegroundColor Yellow
gcloud run services delete $SERVICE --region $REGION --project $PROJECT_ID --quiet

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error al dar de baja el servicio. Es posible que ya haya sido eliminado o no tengas los permisos." -ForegroundColor Red
} else {
    Write-Host "✅ Servicio '$SERVICE' retirado de internet exitosamente." -ForegroundColor Green
}

Write-Host ""
if ($CUSTOM_DOMAIN) {
    Write-Host "[2/4] Eliminando mapeo de dominio ($CUSTOM_DOMAIN)..." -ForegroundColor Yellow
    gcloud run domain-mappings delete --domain $CUSTOM_DOMAIN --region $REGION --project $PROJECT_ID --quiet 2>$null
    Write-Host "✅ Mapeo de dominio eliminado (si existía)." -ForegroundColor Green
} else {
    Write-Host "[2/4] No hay dominio personalizado configurado para eliminar." -ForegroundColor DarkGray
}

Write-Host ""
$saConfirmation = Read-Host "¿Deseas también eliminar la cuenta de servicio '$SERVICE_ACCOUNT'? (S/N)"
if ($saConfirmation -match "^[sS]") {
    Write-Host "[3/4] Eliminando la cuenta de servicio..." -ForegroundColor Yellow
    gcloud iam service-accounts delete $SA_EMAIL --project $PROJECT_ID --quiet
    Write-Host "✅ Cuenta de servicio eliminada." -ForegroundColor Green
} else {
    Write-Host "[3/4] Saltando eliminación de la cuenta de servicio." -ForegroundColor DarkGray
}

Write-Host ""
$secretConfirmation = Read-Host "¿Deseas también eliminar los secretos de Secret Manager (GOOGLE_CLIENT_SECRET, SECRET_KEY, MP_ACCESS_TOKEN)? (S/N)"
if ($secretConfirmation -match "^[sS]") {
    Write-Host "[4/4] Eliminando secretos de Secret Manager..." -ForegroundColor Yellow
    $secrets = @("GOOGLE_CLIENT_SECRET", "SECRET_KEY", "MP_ACCESS_TOKEN")
    foreach ($secret in $secrets) {
        gcloud secrets delete $secret --project $PROJECT_ID --quiet 2>$null
        Write-Host "      Secreto $secret eliminado." -ForegroundColor Green
    }
} else {
    Write-Host "[4/4] Saltando eliminación de secretos." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "🎉 La aplicación y los recursos han sido gestionados." -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green