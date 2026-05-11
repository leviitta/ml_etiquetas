# Script de Despliegue Automatizado para GCP (Google Cloud Platform)
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

# ── Configuración del proyecto de GCP ───────────────────────────────────────
$PROJECT_ID         = $envVars["GCP_PROJECT_ID"]
$REGION             = $envVars["GCP_REGION"]
$REPO               = $envVars["GCP_REPO"]
$SERVICE            = $envVars["GCP_SERVICE"]
$SERVICE_ACCOUNT    = $envVars["GCP_SERVICE_ACCOUNT"]

if (-not $PROJECT_ID -or -not $REGION -or -not $SERVICE) {
    Write-Host "❌ Faltan variables de GCP en el archivo .env (GCP_PROJECT_ID, GCP_REGION, GCP_SERVICE)." -ForegroundColor Red
    exit 1
}

$IMAGE       = "$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/app:latest"

$CUSTOM_DOMAIN = $envVars["CUSTOM_DOMAIN"]
if ($CUSTOM_DOMAIN) {
    $SERVICE_URL = "https://$CUSTOM_DOMAIN"
} else {
    $SERVICE_URL = "https://$SERVICE-890639424998.$REGION.run.app"
}

# Base de datos
$DB_INSTANCE_NAME   = $envVars["DB_INSTANCE_NAME"]
$DB_NAME            = $envVars["DB_NAME"]
$DB_USER            = $envVars["DB_USER"]
$DB_PASSWORD        = $envVars["DB_PASSWORD"]

# Variables normales
$GOOGLE_CLIENT_ID           = $envVars["GOOGLE_CLIENT_ID"]
$FREE_DAILY_QUOTA           = $envVars["FREE_DAILY_QUOTA"]
$FREE_MONTHLY_QUOTA         = $envVars["FREE_MONTHLY_QUOTA"]
$PAID_MONTHLY_QUOTA         = $envVars["PAID_MONTHLY_QUOTA"]
$PAYMENT_DAYS               = $envVars["PAYMENT_DAYS"]
$PAYMENT_PRO_AMOUNT         = $envVars["PAYMENT_PRO_AMOUNT"]
$PAYMENT_INFINITY_AMOUNT    = $envVars["PAYMENT_INFINITY_AMOUNT"]
$PAYMENT_UPGRADE_AMOUNT     = $envVars["PAYMENT_UPGRADE_AMOUNT"]
$REDIRECT_URI               = "$SERVICE_URL/api/v1/auth/callback"

# Secretos
$GOOGLE_CLIENT_SECRET = $envVars["GOOGLE_CLIENT_SECRET"]
$SECRET_KEY           = $envVars["SECRET_KEY"]
$MP_ACCESS_TOKEN      = $envVars["MP_ACCESS_TOKEN"]

# ────────────────────────────────────────────────────────────────────────────

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "🚀 Iniciando despliegue de ML Etiquetas a GCP" -ForegroundColor Cyan
Write-Host "   Proyecto         : $PROJECT_ID"             -ForegroundColor Cyan
Write-Host "   Servicio         : $SERVICE"                -ForegroundColor Cyan
Write-Host "   Cuenta Servicio  : $SERVICE_ACCOUNT"        -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# 0. Verificar Autenticación de Google Cloud para cuenta específica
Write-Host "[0/7] Verificando autenticación de Google Cloud..." -ForegroundColor Yellow
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

# Configurar siempre el proyecto activo y el proyecto de cuota para evitar warnings
Write-Host "      Configurando proyecto activo y de cuotas a: $PROJECT_ID" -ForegroundColor DarkGray
gcloud config set project $PROJECT_ID --quiet
gcloud auth application-default set-quota-project $PROJECT_ID --quiet
Write-Host "      Autenticación y proyecto configurados correctamente." -ForegroundColor Green

Write-Host ""

# 1. Habilitar APIs necesarias
Write-Host "[1/7] Habilitando APIs de Google Cloud..." -ForegroundColor Yellow
gcloud services enable secretmanager.googleapis.com run.googleapis.com cloudbuild.googleapis.com iam.googleapis.com sqladmin.googleapis.com --project $PROJECT_ID

# 2. Gestionar la Cuenta de Servicio
Write-Host "[2/7] Verificando cuenta de servicio..." -ForegroundColor Yellow
$SA_EMAIL = "$SERVICE_ACCOUNT@$PROJECT_ID.iam.gserviceaccount.com"
$saExists = gcloud iam service-accounts describe $SA_EMAIL --project $PROJECT_ID 2>$null

if (-not $saExists) {
    Write-Host "      Creando cuenta de servicio $SERVICE_ACCOUNT..." -ForegroundColor Yellow
    gcloud iam service-accounts create $SERVICE_ACCOUNT --display-name="Service Account for ML Etiquetas" --project $PROJECT_ID
} else {
    Write-Host "      Cuenta de servicio ya existe." -ForegroundColor Green
}

# Ensure service account has Cloud SQL Client permissions
Write-Host "      Asignando rol de Cloud SQL Client a la cuenta de servicio..." -ForegroundColor DarkGray
gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:$SA_EMAIL" `
    --role="roles/cloudsql.client" `
    --condition=None --quiet > $null

# 3. Gestionar Base de Datos (Cloud SQL PostgreSQL)
Write-Host "[3/7] Configurando base de datos Cloud SQL..." -ForegroundColor Yellow
$dbExists = gcloud sql instances describe $DB_INSTANCE_NAME --project $PROJECT_ID 2>$null
if (-not $dbExists) {
    Write-Host "      Creando instancia de PostgreSQL (esto tomará unos minutos)..." -ForegroundColor Yellow
    gcloud sql instances create $DB_INSTANCE_NAME --database-version=POSTGRES_15 --cpu=1 --memory=3840MiB --region=$REGION --project $PROJECT_ID
    Write-Host "      Configurando contraseña de usuario $DB_USER..." -ForegroundColor Yellow
    gcloud sql users set-password $DB_USER --instance=$DB_INSTANCE_NAME --password=$DB_PASSWORD --project $PROJECT_ID
    Write-Host "      Creando base de datos $DB_NAME..." -ForegroundColor Yellow
    gcloud sql databases create $DB_NAME --instance=$DB_INSTANCE_NAME --project $PROJECT_ID
} else {
    Write-Host "      La instancia Cloud SQL ya existe." -ForegroundColor Green
}

# Obtener nombre de conexión de Cloud SQL para Cloud Run
$DB_CONNECTION_NAME = (gcloud sql instances describe $DB_INSTANCE_NAME --format="value(connectionName)" --project $PROJECT_ID).Trim()
$DATABASE_URL_SECRET = "postgresql://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${DB_CONNECTION_NAME}"

# 4. Gestionar Secretos
Write-Host "[4/7] Configurando secretos en Secret Manager..." -ForegroundColor Yellow
$secrets = @{
    "GOOGLE_CLIENT_SECRET" = $GOOGLE_CLIENT_SECRET
    "SECRET_KEY" = $SECRET_KEY
    "MP_ACCESS_TOKEN" = $MP_ACCESS_TOKEN
    "DATABASE_URL" = $DATABASE_URL_SECRET
}

foreach ($secret in $secrets.GetEnumerator()) {
    $secretName = $secret.Key
    $secretValue = $secret.Value
    
    # Crear secreto si no existe
    $secretExists = gcloud secrets describe $secretName --project $PROJECT_ID 2>$null
    if (-not $secretExists) {
        Write-Host "      Creando secreto $secretName..." -ForegroundColor DarkGray
        gcloud secrets create $secretName --replication-policy="automatic" --project $PROJECT_ID
    }
    
    # Agregar versión (evitando el salto de línea oculto y BOM de PowerShell)
    Write-Host "      Añadiendo versión a $secretName..." -ForegroundColor DarkGray
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($secretValue)
    [System.IO.File]::WriteAllBytes("temp_secret.txt", $bytes)
    gcloud secrets versions add $secretName --data-file="temp_secret.txt" --project $PROJECT_ID | Out-Null
    Remove-Item "temp_secret.txt"
    
    # Otorgar permiso a la cuenta de servicio
    gcloud secrets add-iam-policy-binding $secretName `
        --member="serviceAccount:$SA_EMAIL" `
        --role="roles/secretmanager.secretAccessor" `
        --project $PROJECT_ID --quiet > $null
}

# 5. Construir e subir la imagen
Write-Host "[5/7] Construyendo y subiendo la imagen a Artifact Registry..." -ForegroundColor Yellow
gcloud builds submit --config cloudbuild.yaml --project $PROJECT_ID .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error al construir o subir la imagen. Abortando el despliegue." -ForegroundColor Red
    exit 1
}

# 6. Desplegar en Cloud Run (Gen2, con Volumen temporal y Base de datos)
Write-Host "[6/7] Desplegando el contenedor en Google Cloud Run..." -ForegroundColor Yellow
$envVarsString = "GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID," +
                 "FREE_DAILY_QUOTA=$FREE_DAILY_QUOTA," +
                 "FREE_MONTHLY_QUOTA=$FREE_MONTHLY_QUOTA," +
                 "PAID_MONTHLY_QUOTA=$PAID_MONTHLY_QUOTA," +
                 "PAYMENT_DAYS=$PAYMENT_DAYS," +
                 "PAYMENT_PRO_AMOUNT=$PAYMENT_PRO_AMOUNT," +
                 "PAYMENT_INFINITY_AMOUNT=$PAYMENT_INFINITY_AMOUNT," +
                 "PAYMENT_UPGRADE_AMOUNT=$PAYMENT_UPGRADE_AMOUNT," +
                 "REDIRECT_URI=$REDIRECT_URI," +
                 "BASE_URL=$SERVICE_URL"

$secretsString = "GOOGLE_CLIENT_SECRET=GOOGLE_CLIENT_SECRET:latest," +
                 "SECRET_KEY=SECRET_KEY:latest," +
                 "MP_ACCESS_TOKEN=MP_ACCESS_TOKEN:latest," +
                 "DATABASE_URL=DATABASE_URL:latest"

gcloud run deploy $SERVICE `
    --image $IMAGE `
    --region $REGION `
    --platform managed `
    --port 8080 `
    --allow-unauthenticated `
    --memory 2Gi `
    --execution-environment gen2 `
    --add-cloudsql-instances $DB_CONNECTION_NAME `
    --service-account $SA_EMAIL `
    --set-env-vars $envVarsString `
    --set-secrets $secretsString `
    --project $PROJECT_ID

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error al desplegar en Cloud Run." -ForegroundColor Red
    exit 1
}

# 7. Mapear Dominio Personalizado
if ($CUSTOM_DOMAIN) {
    Write-Host ""
    Write-Host "[7/7] Mapeando dominio personalizado $CUSTOM_DOMAIN..." -ForegroundColor Yellow
    # Create the domain mapping.
    gcloud beta run domain-mappings create --service $SERVICE --domain $CUSTOM_DOMAIN --region $REGION --project $PROJECT_ID
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "⚠️ No se pudo crear el mapeo de dominio (puede que ya exista o el dominio no esté verificado en Google Webmaster Central)." -ForegroundColor Yellow
    } else {
        Write-Host "✅ Dominio mapeado." -ForegroundColor Green
        Write-Host "⚠️ IMPORTANTE: Si es la primera vez, asegúrate de configurar los registros DNS indicados por Google en tu proveedor de dominio." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "🎉 Despliegue completado exitosamente." -ForegroundColor Green
Write-Host "   URL del servicio: $SERVICE_URL"            -ForegroundColor Green
Write-Host "   Redirect URI configurada: $REDIRECT_URI"  -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Host "⚠️  IMPORTANTE: Configura tu OAuth Client en Google Cloud Console:" -ForegroundColor Yellow
Write-Host "   1. Orígenes autorizados de JavaScript: $SERVICE_URL" -ForegroundColor Yellow
Write-Host "   2. URIs de redireccionamiento autorizados: $REDIRECT_URI" -ForegroundColor Yellow
Write-Host "   (Ruta: APIs y Servicios → Credenciales → tu OAuth Client ID 'MeliOps')" -ForegroundColor DarkGray
Write-Host ""
Write-Host "💰 MONITOREO Y PRESUPUESTO (Acción Manual Requerida):" -ForegroundColor Cyan
Write-Host "   1. Ve a Google Cloud Console -> Facturación -> Presupuestos y alertas." -ForegroundColor Cyan
Write-Host "   2. Crea un presupuesto (Ej: \$10 USD/mes)." -ForegroundColor Cyan
Write-Host "   3. Activa las alertas por correo al 50%, 90% y 100% de gasto." -ForegroundColor Cyan
Write-Host "   El Cloud Logging ya está activo en tu código para reportar errores." -ForegroundColor Cyan
