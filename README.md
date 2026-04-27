# 🏷️ ML Etiquetas

**Extractor inteligente de etiquetas de envío de MercadoLibre desde archivos PDF.**

Aplicación web construida con **FastAPI** que permite a operadores de logística subir uno o múltiples PDFs de MercadoLibre, extraer automáticamente la etiqueta de cada envío y generar un PDF optimizado listo para imprimir, con soporte de cuadrícula configurable (1, 2, 4 o 6 etiquetas por hoja A4).

---

## 🚀 Características principales

- 📄 **Extracción inteligente de etiquetas** desde PDFs de MercadoLibre usando PyMuPDF (análisis de texto, gráficos e imágenes para detectar el bounding box exacto de la etiqueta)
- 📦 **Procesamiento por lotes** — sube múltiples PDFs en una sola operación
- 🖨️ **Cuadrícula configurable**: 1, 2, 4 o 6 etiquetas por hoja A4
- 🔐 **Autenticación OAuth 2.0 con Google** — solo usuarios autorizados pueden procesar etiquetas
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
│   │       └── auth.py          # Flujo OAuth 2.0 con Google
│   ├── utils/
│   │   └── extract_label.py     # Lógica de extracción y composición de etiquetas
│   └── templates/
│       └── index.html           # Interfaz web (Jinja2)
├── Dockerfile                   # Imagen Docker multi-stage optimizada
├── cloudbuild.yaml              # Pipeline CI/CD en Google Cloud Build
├── compose.yaml                 # Configuración Docker Compose (desarrollo local)
├── deploy_to_gcp.ps1            # Script automatizado de despliegue a Cloud Run
├── undeploy_from_gcp.ps1        # Script para dar de baja el servicio de Cloud Run
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
| Sesiones | Starlette SessionMiddleware |
| Templates | Jinja2 |
| Contenedor | Docker + Python 3.12-slim |
| Package Manager | uv |
| Cloud | Google Cloud Run + Artifact Registry |
| CI/CD | Google Cloud Build |

---

## ⚙️ Variables de entorno

Crea un archivo `.env` en la raíz del proyecto con las siguientes variables:

```env
GOOGLE_CLIENT_ID=tu_client_id_de_google
GOOGLE_CLIENT_SECRET=tu_client_secret_de_google
SECRET_KEY=una_clave_secreta_segura_y_aleatoria
REDIRECT_URI=http://localhost:8000/api/v1/auth/callback
```

> ⚠️ **Nunca subas el archivo `.env` a Git.** Está incluido en `.gitignore`.

---

## 💻 Desarrollo local

### Requisitos previos

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) instalado globalmente
- Docker Desktop (opcional, para correr en contenedor)

### Opción A — Entorno virtual con uv

```bash
# Instalar dependencias
uv sync

# Iniciar la aplicación
uv run uvicorn app.main:app --reload --port 8000
```

Accede en: [http://localhost:8000](http://localhost:8000)

### Opción B — Docker Compose

```bash
docker compose up --build
```

Accede en: [http://localhost:8000](http://localhost:8000)

---

## ☁️ Despliegue en Google Cloud Run

### Requisitos previos

- [Google Cloud SDK (gcloud)](https://cloud.google.com/sdk/docs/install) instalado y autenticado
- Proyecto GCP creado con las siguientes APIs habilitadas:
  - Cloud Run API
  - Cloud Build API
  - Artifact Registry API

### 1. Construir y desplegar

```powershell
.\deploy_to_gcp.ps1
```

El script realizará automáticamente:
1. Leer credenciales del `.env` local
2. Construir la imagen Docker con Cloud Build y subirla a Artifact Registry
3. Desplegar el servicio en Cloud Run con todas las variables de entorno configuradas

### 2. Dar de baja el servicio

```powershell
.\undeploy_from_gcp.ps1
```

Elimina el servicio de Cloud Run (la imagen en Artifact Registry se conserva como respaldo).

### Configuración de OAuth en producción

Después de desplegar, añade la siguiente URI en Google Cloud Console:

```
https://ml-etiquetas-service-890639424998.us-central1.run.app/api/v1/auth/callback
```

**Ruta:** APIs y Servicios → Credenciales → OAuth Client ID → Authorized redirect URIs

---

## 📡 API Reference

### `GET /api/v1/`
Renderiza la interfaz web principal.

### `POST /api/v1/extract`
Procesa uno o múltiples PDFs y devuelve un PDF optimizado.

**Parámetros (form-data):**

| Campo | Tipo | Descripción |
|---|---|---|
| `files` | `File[]` | Uno o más archivos PDF |
| `labels_per_page` | `int` | Etiquetas por hoja: `1`, `2`, `4` o `6` |

**Respuestas:**
- `200 OK` — PDF procesado listo para descargar
- `400 Bad Request` — No se subieron PDFs válidos
- `401 Unauthorized` — Usuario no autenticado
- `500 Internal Server Error` — Error durante el procesamiento

### `GET /api/v1/auth/login`
Inicia el flujo de autenticación con Google OAuth 2.0.

### `GET /api/v1/auth/callback`
Callback de Google. Guarda la sesión del usuario y redirige a la página principal.

### `GET /api/v1/auth/logout`
Cierra la sesión del usuario activo.

---

## 🔄 Historial de cambios

### v1.0.0 — Primera versión de producción (Abril 2026)

#### 🏗️ Arquitectura
- Migración de script CLI a aplicación web con FastAPI
- Estructura modular con routers versionados (`/api/v1/`)
- Separación de responsabilidades: `api/`, `utils/`, `templates/`

#### 🔐 Seguridad
- Implementación de autenticación **Google OAuth 2.0** (Authlib + Starlette SessionMiddleware)
- Protección de la ruta `/extract` — solo usuarios autenticados pueden procesar PDFs
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
- `deploy_to_gcp.ps1` — script completo de despliegue en Cloud Run (lee `.env`, construye imagen, despliega con variables de entorno)
- `undeploy_from_gcp.ps1` — script para dar de baja el servicio de Cloud Run limpiamente
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
