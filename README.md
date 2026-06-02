# 🏷️ ML Etiquetas

**Extractor inteligente de etiquetas de envío de MercadoLibre desde archivos PDF.**

Aplicación web construida con **FastAPI** que permite a operadores de logística subir uno o múltiples PDFs de MercadoLibre, extraer automáticamente la etiqueta de cada envío y generar un PDF optimizado listo para imprimir, con soporte de cuadrícula configurable (1, 2, 4 o 6 etiquetas por hoja A4).

---

## 🚀 Características principales

- 📄 **Extracción inteligente de etiquetas** desde PDFs de MercadoLibre usando PyMuPDF (análisis de texto, gráficos e imágenes para detectar el bounding box exacto de la etiqueta)
- 📦 **Procesamiento por lotes**: sube múltiples PDFs en una sola operación
- 🖨️ **Cuadrícula fija de 2x3**: Composición automática de 6 etiquetas por hoja A4 para optimizar el uso del papel
- 🔍 **Extracción de detalles del producto**: Obtiene información relevante del producto del PDF original y la coloca en una caja gris debajo de cada etiqueta para facilitar la preparación del pedido
- 🔐 **Autenticación OAuth 2.0 con Google**: solo usuarios autorizados pueden procesar etiquetas
- 🖥️ **Interfaz web responsiva** con vista previa dividida (upload + PDF resultado)
- ☁️ **Desplegado en Google Cloud Run** con CI/CD automático via Cloud Build
- 🐳 **Completamente containerizado** con Docker

---

## 🏗️ Arquitectura del proyecto

```
ml_etiquetas/
├── app/
│   ├── main.py                  # Punto de entrada FastAPI + middlewares
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints.py     # Rutas principales (upload / extracción)
│   │       ├── auth.py          # Flujo OAuth 2.0 con Google
│   │       └── payments.py      # Integración de pagos con Mercado Pago
│   ├── db/
│   │   ├── database.py          # Conexión directa a PostgreSQL via asyncpg
│   │   └── quota.py             # Control de cuotas y límites de usuario
│   ├── utils/
│   │   └── extract_label.py     # Lógica de extracción y composición de etiquetas
│   └── templates/
│       └── index.html           # Interfaz web (Jinja2)
├── Dockerfile                   # Imagen Docker multi-stage optimizada
├── cloudbuild.yaml              # Pipeline CI/CD en Google Cloud Build
├── compose.yaml                 # Configuración Docker Compose (desarrollo local)
├── scripts/
│   └── bootstrap.py             # Script de automatización de despliegue y destrucción
├── pyproject.toml               # Dependencias del proyecto (gestionadas con uv)
└── .env                         # Variables de entorno locales (NO incluido en Git)
```

---

## 🛠️ Stack tecnológico

| Componente | Tecnología |
|---|---|
| Backend | FastAPI 0.136+ |
| Servidor ASGI | Uvicorn |
| Extracción PDF | PyMuPDF (fitz) |
| Autenticación | Authlib + Google OAuth 2.0 |
| Base de Datos | PostgreSQL (conexión directa via asyncpg) |
| Control de Cuotas | Sistema de cuotas diarias/mensuales por usuario |
| Pasarela de Pagos | Mercado Pago (integración directa via HTTPX) |
| Sesiones | Starlette SessionMiddleware |
| Templates | Jinja2 |
| Contenedor | Docker + Python 3.12-slim |
| Package Manager | uv |
| Cloud | Google Cloud Run + Cloud SQL + Artifact Registry |
| CI/CD | GitHub Actions + Google Cloud Build |

---

## ⚙️ Variables de entorno

Crea un archivo `.env` en la raíz del proyecto con las siguientes variables:

```env
# Autenticación Google OAuth 2.0
GOOGLE_CLIENT_ID=tu_client_id_de_google
GOOGLE_CLIENT_SECRET=tu_client_secret_de_google
SECRET_KEY=una_clave_secreta_segura_y_aleatoria
REDIRECT_URI=http://localhost:8000/api/v1/auth/callback

# Base de Datos (PostgreSQL)
DB_HOST=localhost
DB_USER=postgres
DB_PASSWORD=mypassword123
DB_NAME=mldb
DATABASE_URL=postgresql://postgres:mypassword123@localhost/mldb

# Mercado Pago
MP_ACCESS_TOKEN=tu_access_token_de_mercado_pago
MP_WEBHOOK_SECRET=tu_webhook_secret_de_mercado_pago
BASE_URL=http://localhost:8000

# Precios y Cuotas
PAYMENT_PRO_AMOUNT=4990
PAYMENT_INFINITY_AMOUNT=12990
PAYMENT_UPGRADE_AMOUNT=8000
PAYMENT_DAYS=30
FREE_DAILY_QUOTA=5
FREE_MONTHLY_QUOTA=20
PAID_MONTHLY_QUOTA=100

# Pruebas (Testing)
TESTING=true
TESTING_WITH_REAL_DB=1
```

### Descripción de las variables

#### Autenticación
- `GOOGLE_CLIENT_ID`: Identificador de cliente para Google OAuth.
- `GOOGLE_CLIENT_SECRET`: Clave secreta para Google OAuth.
- `SECRET_KEY`: Semilla secreta para firmar las sesiones de usuario.
- `REDIRECT_URI`: URL de retorno para el flujo de autenticación.

#### Base de Datos
- `DB_HOST`: Dirección del servidor de base de datos.
- `DB_USER`: Usuario de PostgreSQL.
- `DB_PASSWORD`: Contraseña de PostgreSQL.
- `DB_NAME`: Nombre de la base de datos.
- `DATABASE_URL`: URL de conexión completa. Si se define, tiene prioridad sobre las variables individuales.

#### Mercado Pago
- `MP_ACCESS_TOKEN`: Token de acceso de Mercado Pago para procesar pagos.
- `MP_WEBHOOK_SECRET`: Clave secreta para validar la firma de las notificaciones webhook.
- `BASE_URL`: URL base pública de la aplicación para configurar retornos y webhooks.

#### Precios y Cuotas
- `PAYMENT_PRO_AMOUNT`: Precio del plan Pro en pesos chilenos.
- `PAYMENT_INFINITY_AMOUNT`: Costo del plan Infinity en pesos chilenos.
- `PAYMENT_UPGRADE_AMOUNT`: Valor para subir de Pro a Infinity.
- `PAYMENT_DAYS`: Duración en días de los planes de pago.
- `FREE_DAILY_QUOTA`: Límite diario de etiquetas para usuarios gratuitos.
- `FREE_MONTHLY_QUOTA`: Cantidad mensual de etiquetas para usuarios gratuitos.
- `PAID_MONTHLY_QUOTA`: Cuota mensual adicional otorgada por cada pago Pro.

#### Pruebas
- `TESTING`: Activa el modo de pruebas para omitir ciertas validaciones.
- `TESTING_WITH_REAL_DB`: Define si las pruebas deben ejecutarse usando una base de datos PostgreSQL real en lugar de mocks.

> ⚠️ **Nunca subas el archivo `.env` a Git.** Está incluido en `.gitignore`.

---

## 💻 Desarrollo local

### Requisitos previos

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) instalado globalmente
- Docker Desktop (opcional, para correr en contenedor)

### Opción A, Entorno virtual con uv

```bash
# Instalar dependencias
uv sync

# Iniciar la aplicación
uv run uvicorn app.main:app --reload --port 8000
```

Accede en: [http://localhost:8000](http://localhost:8000)

### Opción B, Docker Compose

```bash
docker compose up --build
```

Accede en: [http://localhost:8000](http://localhost:8000)

---

## ☁️ Despliegue en Google Cloud Run

El despliegue principal se realiza de forma automática mediante **GitHub Actions** al hacer push a la rama `main`. Este pipeline de CI/CD ejecuta las pruebas unitarias, se autentica en Google Cloud usando Workload Identity Federation, compila la imagen y aplica los cambios de infraestructura con Terraform.

Para despliegues locales, manuales o configuración inicial de la infraestructura, se utiliza el script de automatización `scripts/bootstrap.py`.

### Requisitos previos para despliegue manual

- [Google Cloud SDK (gcloud)](https://cloud.google.com/sdk/docs/install) instalado y autenticado.
- Proyecto GCP creado con las APIs necesarias habilitadas (Cloud Run, Cloud Build, Artifact Registry, Cloud SQL).
- Terraform instalado localmente.

### 1. Configuración inicial y despliegue manual

```bash
python scripts/bootstrap.py
```

El script realiza las siguientes acciones de forma automática:
1. Detecta la cuenta activa de GCP.
2. Lee las credenciales del archivo `.env` local.
3. Genera el archivo `terraform/terraform.tfvars.json` dinámicamente con el tag de la imagen correspondiente (Git SHA o tag con sufijo `-dirty` si hay cambios sin confirmar).
4. Crea el bucket de GCS para almacenar el estado de Terraform si no existe.
5. Inicializa Terraform y aplica de forma dirigida el repositorio de Artifact Registry.
6. Construye la imagen Docker con Cloud Build y la sube a Artifact Registry con el tag correspondiente y `latest`.
7. Ejecuta el despliegue completo final con Terraform.

### 2. Destrucción de recursos (Dar de baja el servicio)

```bash
python scripts/bootstrap.py --destroy
```

Inicializa Terraform y ejecuta `terraform destroy -auto-approve` para eliminar de forma limpia todos los recursos creados en GCP.

### Configuración de OAuth en producción

Después de desplegar, añade la siguiente URI en Google Cloud Console:

```
https://ml-etiquetas-service-890639424998.us-central1.run.app/api/v1/auth/callback
```

**Ruta:** APIs y Servicios, Credenciales, OAuth Client ID, Authorized redirect URIs

---

## 📡 API Reference

### `GET /`
Redirige automáticamente a la ruta principal de la API `/api/v1/`.

### `GET /robots.txt`
Archivo de configuración para rastreadores web y SEO.

### `GET /sitemap.xml`
Mapa del sitio en formato XML para indexación en motores de búsqueda.

### `GET /api/v1/`
Renderiza la interfaz web principal de la aplicación.

### `GET /faq`
Renderiza la página de preguntas frecuentes (FAQ).

### `POST /api/v1/extract`
Procesa uno o múltiples archivos PDF de MercadoLibre. Extrae las etiquetas de envío y genera un único PDF optimizado con una cuadrícula fija de 2x3 (6 etiquetas por hoja A4). También extrae los detalles del producto y los coloca en una caja gris debajo de cada etiqueta.

**Parámetros (form-data):**

| Campo | Tipo | Descripción |
|---|---|---|
| `files` | `File[]` | Uno o más archivos PDF (límite de 200 KB por archivo) |

**Respuestas:**
- `200 OK`: PDF procesado listo para descargar.
- `400 Bad Request`: No se subieron archivos válidos o superan el límite de tamaño.
- `403 Forbidden`: Cuota de uso diaria o mensual excedida.
- `500 Internal Server Error`: Error durante el procesamiento del PDF.

### `POST /api/v1/quota/register`
Registra el uso de cuota en la base de datos cuando el usuario descarga las etiquetas procesadas.

**Cuerpo de la solicitud (JSON):**
```json
{
  "count": 1
}
```

**Respuestas:**
- `200 OK`: `{"success": true}`
- `400 Bad Request`: `{"error": "Sesión inválida."}`

### `POST /api/v1/payments/create-preference`
Crea una preferencia de pago en Mercado Pago para adquirir un plan de cuotas extendido.

**Cuerpo de la solicitud (JSON):**
```json
{
  "plan_type": "pro"
}
```
*Valores posibles para `plan_type`: `"pro"`, `"infinity"`.*

**Respuestas:**
- `200 OK`: Devuelve los puntos de inicio del checkout de Mercado Pago y el ID de la preferencia.
  ```json
  {
    "init_point": "https://www.mercadopago.cl/sandbox/... ",
    "sandbox_init_point": "https://sandbox.mercadopago.cl/... ",
    "preference_id": "..."
  }
  ```
- `401 Unauthorized`: `{"error": "Debes iniciar sesión."}`
- `500 Internal Server Error` / `502 Bad Gateway`: Error al conectar con Mercado Pago.

### `GET /api/v1/payments/success`
Callback de redirección de Mercado Pago tras un pago aprobado. Verifica el estado real de la transacción mediante la API de Mercado Pago, registra el pago en la base de datos y redirige al home con el parámetro `?payment=success`.

### `GET /api/v1/payments/failure`
Callback de redirección de Mercado Pago tras un pago fallido. Redirige al home con el parámetro `?payment=failure`.

### `GET /api/v1/payments/pending`
Callback de redirección de Mercado Pago tras un pago pendiente. Redirige al home con el parámetro `?payment=pending`.

### `POST /api/v1/payments/webhook`
Webhook IPN de Mercado Pago. Recibe notificaciones asíncronas de eventos de pago. Valida la firma HMAC-SHA256 de la solicitud, consulta el estado del pago en la API de Mercado Pago y actualiza la base de datos si el pago fue aprobado.

### `GET /api/v1/auth/login`
Inicia el flujo de autenticación con Google OAuth 2.0.

### `GET /api/v1/auth/callback`
Callback de Google OAuth 2.0. Guarda la sesión del usuario y redirige a la página principal.

### `GET /api/v1/auth/logout`
Cierra la sesión del usuario activo.

---

## 🔄 Historial de cambios

### v1.0.0, Primera versión de producción (Abril 2026)

#### 🏗️ Arquitectura
- Migración de script CLI a aplicación web con FastAPI
- Estructura modular con routers versionados (`/api/v1/`)
- Separación de responsabilidades: `api/`, `utils/`, `templates/`

#### 🔐 Seguridad
- Implementación de autenticación **Google OAuth 2.0** (Authlib + Starlette SessionMiddleware)
- Protección de la ruta `/extract`, solo usuarios autenticados pueden procesar PDFs
- Variables de entorno para secretos (nunca hardcodeados en el código)
- `.env` excluido de Git mediante `.gitignore`

#### 📄 Extracción de etiquetas
- Algoritmo de detección de bounding box que analiza texto, dibujos vectoriales e imágenes (códigos QR/barras)
- Soporte para procesar la etiqueta únicamente desde la mitad izquierda del PDF (formato estándar de MercadoLibre)

#### 📦 Procesamiento por lotes
- Upload simultáneo de múltiples PDFs desde la interfaz web
- Composición en cuadrícula configurable: 1, 2, 4 o 6 etiquetas por hoja A4
- Tamaño uniforme de etiquetas independientemente de la configuración seleccionada
- Archivos temporales con limpieza automática después del envío (`BackgroundTasks`)

#### 🖥️ Interfaz web
- Interfaz split-screen responsiva: panel de upload + visor de PDF en tiempo real
- Indicador de estado y autenticación con foto de perfil del usuario de Google
- Visor de PDF integrado sin barra de herramientas del navegador

#### 🐳 Containerización
- `Dockerfile` optimizado usando Python 3.12-slim
- Gestión de dependencias con `uv` (más rápido que pip)
- `.dockerignore` para excluir archivos innecesarios del contenedor
- `compose.yaml` para desarrollo local con Docker Compose

#### ☁️ Infraestructura GCP
- `cloudbuild.yaml` para CI/CD automático (build + push a Artifact Registry)
- `scripts/bootstrap.py` para automatizar la compilación local, configuración de Terraform y despliegue completo
- Servicio desplegado en `us-central1` con 2GB de memoria

---

## 📋 Requisitos del archivo `.gitignore`

El proyecto excluye de Git los siguientes archivos sensibles:

```
.env
.venv/
__pycache__/
*.pyc
```

---

## 📄 Licencia

Este proyecto es de uso interno. Todos los derechos reservados.
