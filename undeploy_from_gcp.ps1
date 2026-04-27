# Script para Bajar la Aplicación de GCP (Google Cloud Platform)
# Ejecuta este script desde la terminal de Windows PowerShell

# ── Configuración del proyecto ──────────────────────────────────────────────
$PROJECT_ID = "ml-etiquetas"
$REGION     = "us-central1"
$SERVICE    = "ml-etiquetas-service"
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
Write-Host "[1/1] Eliminando el servicio de Google Cloud Run..." -ForegroundColor Yellow
gcloud run services delete $SERVICE --region $REGION --project $PROJECT_ID --quiet

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error al dar de baja el servicio. Es posible que ya haya sido eliminado o no tengas los permisos." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "✅ Servicio '$SERVICE' retirado de internet exitosamente." -ForegroundColor Green
Write-Host ""
Write-Host "(Nota: La imagen de Docker precompilada todavía existe en tu base de datos de Google Artifact Registry como backup, pero ya no está corriendo en ningún servidor)." -ForegroundColor DarkGray
Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "🎉 La aplicación ha sido dada de baja." -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
