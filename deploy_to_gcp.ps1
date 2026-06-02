if (-not (Test-Path .env)) {
    Write-Host "❌ No se encontró el archivo .env." -ForegroundColor Red
    exit 1
}

$envVars = @{}
Get-Content .env | Where-Object { $_ -match "^\s*[^#].*=.*" } | ForEach-Object {
    $parts = $_ -split "=", 2
    $envVars[$parts[0].Trim()] = $parts[1].Trim()
}

$PROJECT_ID = $envVars["GCP_PROJECT_ID"]
$REGION     = $envVars["GCP_REGION"]
$REPO       = $envVars["GCP_REPO"]
$SERVICE    = $envVars["GCP_SERVICE"]

if (-not $PROJECT_ID -or -not $REGION -or -not $SERVICE) {
    Write-Host "❌ Faltan variables de GCP en el archivo .env (GCP_PROJECT_ID, GCP_REGION, GCP_SERVICE)." -ForegroundColor Red
    exit 1
}

$IMAGE = "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/app:latest"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "🚀 Iniciando despliegue de ML Etiquetas a GCP" -ForegroundColor Cyan
Write-Host "   Proyecto : $PROJECT_ID"                     -ForegroundColor Cyan
Write-Host "   Servicio : $SERVICE"                        -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Verificando autenticación de Google Cloud..." -ForegroundColor Yellow
$TARGET_ACCOUNT = "av.diazh@gmail.com"
$activeAccount = gcloud config get-value account 2>$null

if ($activeAccount -ne $TARGET_ACCOUNT) {
    Write-Host "      Cuenta activa ($activeAccount) no coincide con $TARGET_ACCOUNT. Forzando login..." -ForegroundColor Cyan
    gcloud config set account $TARGET_ACCOUNT
    gcloud auth login $TARGET_ACCOUNT
    gcloud auth application-default login
} else {
    Write-Host "      Sesión correcta detectada: $TARGET_ACCOUNT" -ForegroundColor Green
}

gcloud config set project $PROJECT_ID --quiet
gcloud auth application-default set-quota-project $PROJECT_ID --quiet

Write-Host "[2/3] Construyendo y subiendo la imagen a Artifact Registry..." -ForegroundColor Yellow
gcloud builds submit --config cloudbuild.yaml --project $PROJECT_ID .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error al construir o subir la imagen. Abortando el despliegue." -ForegroundColor Red
    exit 1
}

Write-Host "[3/3] Desplegando el contenedor en Google Cloud Run..." -ForegroundColor Yellow
gcloud run deploy $SERVICE `
    --image $IMAGE `
    --region $REGION `
    --project $PROJECT_ID

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error al desplegar en Cloud Run." -ForegroundColor Red
    exit 1
}

Write-Host "=============================================" -ForegroundColor Green
Write-Host "🎉 Despliegue completado exitosamente." -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
