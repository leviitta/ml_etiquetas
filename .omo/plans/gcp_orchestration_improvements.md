# Plan de Trabajo: Mejora en la Orquestación de GCP, CI/CD y Pruebas de Integración

## 1. Resumen y Objetivos

Este plan detalla la migración de la infraestructura de GCP de un modelo imperativo basado en PowerShell a un modelo declarativo usando **Terraform/OpenTofu**. También establece un pipeline de integración y despliegue continuo (CI/CD) con **GitHub Actions** y automatiza las pruebas de integración utilizando una base de datos PostgreSQL real en la suite de pruebas.

### Criterios de Éxito
- Toda la infraestructura de GCP (Cloud Run, Cloud SQL, Secret Manager, IAM, WIF) se gestiona de forma declarativa con Terraform.
- El despliegue de la infraestructura se realiza de manera segura mediante el estado de Terraform almacenado en una cubeta GCS.
- Pipeline de GitHub Actions que corre de manera automática en cada push: ejecuta linter (black/flake8/ruff), ejecuta la suite completa de tests (con base de datos real en un contenedor de servicio) y despliega automáticamente a Cloud Run utilizando Workload Identity Federation (WIF).
- Suite de pruebas de FastAPI extendida para soportar pruebas de integración reales sobre PostgreSQL de forma opcional (`TESTING_WITH_REAL_DB=1`), con limpieza automática (truncado) entre pruebas.

---

## 2. Arquitectura y Alcance

### En Alcance (IN)
- **Directorio `terraform/`**: Creación de archivos de Terraform (`main.tf`, `variables.tf`, `outputs.tf`, `providers.tf`) que declaren todos los recursos de GCP requeridos.
- **WIF (Workload Identity Federation)**: Configuración en GCP y Terraform para autenticar a GitHub Actions sin necesidad de llaves de cuentas de servicio en texto plano.
- **Workflow de GitHub Actions (`.github/workflows/deploy.yml`)**: Pipeline que ejecuta tests de integración con un contenedor de PostgreSQL, compila la imagen Docker con cache, la sube a Artifact Registry y la despliega en Cloud Run.
- **Refactorización de `tests/conftest.py`**: Añadir soporte condicional para conectar a base de datos PostgreSQL real (por ejemplo local en docker o en el contenedor de servicios de CI) y limpiar tablas mediante `TRUNCATE` entre ejecuciones de prueba.
- **Pruebas de Integración**: Crear un archivo de pruebas de integración para verificar operaciones reales de cuota e inserciones de usuario sobre la base de datos PostgreSQL.

### Fuera de Alcance (OUT)
- Migración de la base de datos de producción a otra tecnología.
- Modificaciones en la interfaz de usuario de la aplicación o lógica de extracción de PDFs.
- Automatización de la compra de planes de Mercado Pago.

---

## 3. Decisiones Clave y Mitigación de Riesgos

| Riesgo | Decisión Técnica / Mitigación |
| --- | --- |
| **Exposición de Secretos en Terraform** | Terraform creará los contenedores de secretos en GCP Secret Manager con valores iniciales dummy. Los valores reales de producción se insertarán de forma manual (fuera de banda) directamente en Secret Manager para mantener seguro el archivo de estado de Terraform (`terraform.tfstate`). |
| **Problema "Huevo y Gallina" de Cloud Run** | Terraform requiere una imagen Docker válida para crear el servicio de Cloud Run por primera vez, pero GitHub Actions necesita el servicio para desplegar. **Mitigación**: Terraform desplegará inicialmente una imagen de marcador de posición liviana (`gcr.io/cloudrun/hello`). El workflow de GitHub Actions sobrescribirá esta imagen con la compilación real del proyecto. |
| **Fricción en Desarrollo Local** | Si forzamos la base de datos real para todas las pruebas locales, los desarrolladores que no tengan PostgreSQL instalado localmente verán fallar las pruebas. **Mitigación**: `conftest.py` usará la base de datos real *solo* si se define la variable de entorno `TESTING_WITH_REAL_DB=1` o se provee un `DATABASE_URL` válido; de lo contrario, por defecto seguirá usando mocks. |
| **Fricción de Estado en Pruebas de Integración** | Ejecutar pruebas sobre una DB real puede dejar datos residuales afectando pruebas subsiguientes. **Mitigación**: Implementar un fixture en `conftest.py` que ejecute un comando `TRUNCATE TABLE users, quota_usage, payments CASCADE;` antes/después de cada test de integración. |
| **Riesgo de Escalada de Privilegios (SA)** | Usar una sola cuenta de servicio para ejecución y despliegue expone la infraestructura. **Mitigación**: Crear dos cuentas independientes (`ml-etiquetas-run-sa` para ejecución con menor privilegio, y `ml-etiquetas-deploy-sa` para despliegue por CI/CD). |
| **Borrado Accidental de Base de Datos** | Sin protección contra eliminación, comandos accidentales pueden destruir Cloud SQL. **Mitigación**: Declarar `deletion_protection = true` en producción de la base de datos. |
| **Despliegues no Deterministas (Latest)** | Usar la etiqueta `latest` impide rollbacks fiables. **Mitigación**: GitHub Actions etiquetará las imágenes Docker con el Git Commit SHA (`github.sha`). |
| **Construcción Lenta de Imágenes Docker** | Sin caché de compilación, el pipeline CI/CD consume excesivo tiempo. **Mitigación**: Configurar `docker/build-push-action` con caché remoto en GitHub Actions Cache. |

---

## 4. Fase de Preparación (Bootstrap)

Antes de ejecutar Terraform por primera vez, se requiere preparar el entorno mínimo en GCP de manera manual o mediante un script simple de bootstrap:
1. Crear una cubeta GCS (ej. `ml-etiquetas-tf-state`) para almacenar de forma segura el estado de Terraform.
2. Habilitar la API de Cloud Resource Manager en el proyecto GCP de destino.

---

## 5. Tareas Detalladas de Implementación

### - [x] Tarea 1: Configurar la Infraestructura Declarativa con Terraform
- **Objetivo**: Crear toda la configuración de Terraform para declarar y aprovisionar los recursos de GCP de manera segura.
- **Archivos a Crear/Modificar**:
  - `terraform/providers.tf`: Configurar el proveedor de Google y el backend GCS para almacenar el estado remoto.
  - `terraform/variables.tf`: Declarar variables de configuración (project_id, region, db_name, db_user, variables de entorno de la app).
  - `terraform/main.tf`: Declarar los siguientes recursos:
    - APIs habilitadas (Cloud Run, Cloud SQL, Secret Manager, IAM, WIF).
    - Instancia de Cloud SQL PostgreSQL 15 (`db-f1-micro`) con configuración de auto-crecimiento de almacenamiento, copias de seguridad y **`deletion_protection = true`** para evitar el borrado accidental de la base de datos de producción.
    - Base de datos y usuario de base de datos.
    - Secretos en Secret Manager (como contenedores vacíos para evitar la exposición de secretos en el estado de Terraform).
    - **Dos Cuentas de Servicio Diferentes (Principio de Menor Privilegio)**:
      - `ml-etiquetas-run-sa`: Utilizada únicamente para la ejecución del contenedor en Cloud Run. Con permisos mínimos: acceso a secretos (`roles/secretmanager.secretAccessor`) e integración con Cloud SQL (`roles/cloudsql.client`).
      - `ml-etiquetas-deploy-sa`: Utilizada exclusivamente por el pipeline de CI/CD (GitHub Actions) a través de Workload Identity Federation (WIF) para compilar y desplegar la aplicación.
    - Servicio de Cloud Run Gen2 apuntando inicialmente a la imagen dummy `gcr.io/cloudrun/hello` (con la cuenta de servicio de ejecución `ml-etiquetas-run-sa` vinculada). Montar secretos de Secret Manager como variables de entorno y configurar la conexión de Cloud SQL.
    - Workload Identity Pool y Provider para autenticar a GitHub Actions de forma segura usando la cuenta de servicio de despliegue `ml-etiquetas-deploy-sa`.
  - `terraform/outputs.tf`: Exportar el string del proveedor de WIF (`workload_identity_provider`), el email de la cuenta de servicio de despliegue y la URL de Cloud Run.
- **QA / Verificación**:
  - Inicializar Terraform localmente: `terraform init`.
  - Ejecutar validación de sintaxis y plan: `terraform validate && terraform plan`. Verificar que la lista de recursos planeados sea correcta (11+ recursos nuevos, confirmando ambas SAs y la protección contra eliminación).

### - [x] Tarea 2: Adaptar `tests/conftest.py` para Pruebas de Integración con Base de Datos Real
- **Objetivo**: Permitir que pytest realice pruebas de integración reales sobre PostgreSQL de forma opcional y mantenga un estado limpio entre pruebas de forma segura y compatible con Python 3.12.
- **Archivos a Crear/Modificar**:
  - `tests/conftest.py`:
    - Leer la variable de entorno `TESTING_WITH_REAL_DB` (por ejemplo, `TESTING_WITH_REAL_DB=1`).
    - Si es falso (por defecto), mantener la lógica de mockeo de `app.db.database.init_db`. **Mejora**: Mover el patcher a una fixture con cleanup explícito (evitando el `patcher.start()` a nivel de módulo sin `stop()`).
    - Si es verdadero:
      - Evitar aplicar el parche mock de `init_db`.
      - Asegurar que la URL de conexión `DATABASE_URL` se configure dinámicamente apuntando a la base de datos de pruebas (por ejemplo, `postgresql://postgres:mypassword123@localhost/mldb`).
      - Iniciar el pool de base de datos llamando a `await init_db()` real.
      - Crear un fixture autouse con scope `function` (ej. `clean_database`) que, antes y después de cada prueba, ejecute:
        ```sql
        TRUNCATE TABLE users, quota_usage, payments CASCADE;
        ```
        Esto garantiza que cada prueba comience con una base de datos vacía e independiente.
    - **Mejora Python 3.12 Event Loop**: Evitar el uso obsoleto de `get_event_loop()` en los fixtures de pytest-asyncio, definiendo una fixture `event_loop` moderna de pytest-asyncio para gestionar de forma limpia el bucle de eventos asíncronos.
- **QA / Verificación**:
  - Levantar un contenedor local de PostgreSQL con Docker Compose: `docker compose up -d db`.
  - Ejecutar `TESTING_WITH_REAL_DB=1 pytest` localmente. Verificar que la suite pase sin advertencias obsoletas de `get_event_loop()` y que las tablas se limpien e inicialicen correctamente entre ejecuciones.

### - [x] Tarea 3: Crear Casos de Pruebas de Integración Reales
- **Objetivo**: Escribir pruebas específicas para validar el comportamiento real de cuotas, registros de pagos y persistencia en la base de datos sin usar mocks.
- **Archivos a Crear/Modificar**:
  - `tests/test_integration_db.py`: Crear un nuevo archivo de pruebas que contenga:
    - Decorador para omitir si no está activo el modo real: `@pytest.mark.skipif(not os.getenv("TESTING_WITH_REAL_DB"), reason="Requiere base de datos de pruebas real")`.
    - `test_ensure_user_integration`: Llama a `ensure_user("test@example.com", "Test User")`, luego consulta directamente la tabla `users` mediante una conexión obtenida con `get_db()` para verificar que el registro realmente existe.
    - `test_register_usage_and_quota_integration`: Registra uso de cuota con `register_usage` múltiples veces y valida que `get_quota_status` refleje el consumo correcto y que al exceder el límite, `verify_quota_for_batch` lance `QuotaExceededException`.
    - `test_register_payment_integration`: Registra un pago aprobado para un plan, y verifica que el límite de cuota diario y mensual de `get_quota_status` se actualice de forma asíncrona acorde al plan comprado.
- **QA / Verificación**:
  - Ejecutar `pytest tests/test_integration_db.py` localmente con `TESTING_WITH_REAL_DB=1` activo.
  - Verificar que las pruebas de integración pasen y que no queden datos residuales en las tablas `users`, `quota_usage` o `payments` al finalizar gracias al fixture de limpieza de la Tarea 2.

### - [x] Tarea 4: Configurar el Pipeline de CI/CD con GitHub Actions
- **Objetivo**: Automatizar la ejecución de análisis estático, suite completa de pruebas, compilación de imagen Docker y despliegue a Cloud Run en GCP usando autenticación WIF segura con la cuenta de despliegue dedicada, caché optimizada y etiquetado inmutable por SHA.
- **Archivos a Crear/Modificar**:
  - `.github/workflows/deploy.yml`: Crear el archivo de definición de workflow con dos trabajos principales:
    - **Job `test`**:
      - Ejecutar sobre un runner `ubuntu-latest`.
      - Iniciar un contenedor de servicio de base de datos de PostgreSQL `postgres:15` en el runner (configurar puertos, variables de contraseña y base de datos predeterminada `mldb`).
      - Descargar el repositorio, instalar python y `uv`.
      - Ejecutar `uv pip install -e .[dev]` o similar para sincronizar dependencias.
      - Correr control de formateo y estilo con Ruff u otra herramienta de análisis estático del repo.
      - Ejecutar pytest con `TESTING_WITH_REAL_DB=1` y configurando `DATABASE_URL` para conectarse al servicio local PostgreSQL de GitHub Actions (`postgresql://postgres:mypassword123@localhost:5432/mldb`).
    - **Job `deploy`**:
      - Requiere que el job `test` termine con éxito y que se ejecute en la rama principal (`main` o `master`).
      - Autenticarse en Google Cloud utilizando la acción oficial `google-github-actions/auth` mediante Workload Identity Federation (WIF) utilizando el WIF provider y el email de la **cuenta de servicio de despliegue (`ml-etiquetas-deploy-sa`)** exportados por Terraform.
      - Configurar la autenticación de Docker en el Artifact Registry de GCP.
      - **Optimización de Caché y Compilación**: Utilizar la acción `docker/build-push-action` con soporte de caché (`cache-from: type=gha`, `cache-to: type=gha,mode=max`) para reducir el tiempo de compilación.
      - **Etiquetado Determinista (Inmutable)**: Compilar y subir la imagen Docker usando como etiqueta el **Git Commit SHA (`${{ github.sha }}`)** en lugar de `latest`, asegurando trazabilidad y rollbacks seguros.
      - Desplegar la imagen con el SHA específico a Cloud Run utilizando la acción `google-github-actions/deploy-cloudrun` (esto sobrescribirá la imagen dummy de Hello World inicial de Terraform).
- **QA / Verificación**:
  - Realizar un push a la rama de pruebas y verificar que el workflow de GitHub Actions se active de forma automática.
  - Monitorear que la base de datos de servicio se levante correctamente en el runner, que todas las pruebas (incluyendo las de integración reales) pasen con éxito, que las capas de Docker usen la caché de GHA, y que el despliegue a Cloud Run finalice utilizando el tag de SHA inmutable y la Service Account de despliegue correcta.

---

## Final Verification Wave

### Criterios de Aceptación Técnicos
- **Verificación IaC**: `terraform plan` se ejecuta de forma limpia y `terraform apply` crea todos los recursos necesarios con una imagen dummy de Cloud Run.
- **Verificación CI/CD**: Un push a la rama principal (o un PR) activa el workflow de GitHub Actions que:
  1. Ejecuta tests con una base de datos PostgreSQL de servicio y pasa con éxito.
  2. Compila la imagen y la sube a Artifact Registry de forma autenticada.
  3. Despliega el contenedor final en Cloud Run mediante WIF con éxito.
- **Verificación de Pruebas**: Ejecutar `TESTING_WITH_REAL_DB=1 pytest` de manera local o en CI demuestra que los tests de integración escriben en la base de datos, verifican cuotas y limpian las tablas correctamente.

### Firma del Usuario
El implementador NO marcará este plan como completado hasta que el usuario revise los logs del despliegue exitoso en GitHub Actions y proporcione un consentimiento explícito.
