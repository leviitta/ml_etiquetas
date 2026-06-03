# Plan de Trabajo: Automatización de Bootstrap GCS y Sincronización de Secretos `.env` en GCP

## 1. Resumen y Objetivos

Este plan detalla la automatización completa del flujo de aprovisionamiento en GCP. Integra un script de inicialización (**bootstrap**) en Python que autogestiona la creación del bucket de estado de Terraform, y añade soporte nativo en Terraform para parsear el archivo `.env` local. Esto inyecta de manera 100% declarativa los secretos reales en Secret Manager y asocia sus números de versión de forma inmutable al servicio Cloud Run (evitando la referencia `latest`), eliminando todo el "Paso 2" manual de configuración de secretos.

### Criterios de Éxito
- La creación del bucket de estado de Terraform (`ml-etiquetas-tf-state` o similar basado en el ID del proyecto) está 100% automatizada e idempotente a través de un script multiplataforma en Python.
- Terraform parsea de manera nativa el archivo `.env` local para extraer de forma automática y declarativa los valores de secretos (`SECRET_KEY`, `GOOGLE_CLIENT_SECRET`, `MP_ACCESS_TOKEN`).
- La `DATABASE_URL` de producción se genera de manera dinámica en los locales de Terraform, inyectando de forma segura el Socket Unix de Cloud SQL y codificando la contraseña mediante `urlencode()`.
- Los secretos en Cloud Run se vinculan a sus versiones específicas administradas por Terraform (ej. `version = "1"` en lugar de `latest`), forzando una nueva revisión/despliegue de Cloud Run cada vez que un secreto cambia.
- El pipeline de despliegue en GitHub Actions y el script de PowerShell se refactorizan para separar responsabilidades: Terraform gestiona la configuración y las versiones de secretos, mientras que el despliegue de CI/CD solo actualiza la imagen del contenedor.

---

## 2. Arquitectura y Alcance

### En Alcance (IN)
- **`scripts/bootstrap.py`**: Nuevo script de bootstrap idempotente en Python que gestiona el bucket GCS remoto y ejecuta `terraform init/apply`.
- **`terraform/providers.tf`**: Omitir el bucket hardcodeado en la configuración del backend para habilitar inicialización parcial y dinámica.
- **`terraform/variables.tf`**: Declarar variables sensibles fallback para secretos, asegurando compatibilidad en pipelines de CI/CD.
- **`terraform/main.tf`**:
  - Implementar el parser nativo de `.env` en los `locals` de Terraform.
  - Declarar recursos `google_secret_manager_secret_version` para inyectar automáticamente los valores.
  - Compilar dinámicamente la `DATABASE_URL` con codificación segura.
  - Modificar el recurso de Cloud Run para vincular las variables de secreto a la versión inmutable declarada.
- **`.github/workflows/deploy.yml` y `deploy_to_gcp.ps1`**: Refactorizar para omitir `--set-secrets` de los comandos `gcloud run deploy`, preservando el control de configuración en Terraform.

### Fuera de Alcance (OUT)
- Gestión de dominios fuera de Terraform.
- Cambios en el código de backend de la aplicación FastAPI.

---

## 3. Decisiones Clave y Mitigación de Riesgos

| Riesgo | Decisión Técnica / Mitigación |
| --- | --- |
| **Secretos expuestos en State GCS** | Terraform guarda valores de secretos en texto plano en su estado. **Mitigación**: El script de bootstrap asegurará que el bucket GCS tenga habilitado el cifrado por defecto, desactivado el acceso público (Public Access Prevention) y políticas IAM ultra-restrictivas. |
| **Falta de `.env` en GHA / CI/CD** | GitHub Actions no tiene un archivo `.env` en su runner, lo que rompería la lectura nativa de Terraform. **Mitigación**: Usar `fileexists()` en Terraform; si no existe `.env`, Terraform usará variables fallback que se inyectarán de forma segura en CI/CD vía secretos de GitHub (`TF_VAR_*`). |
| **Despliegues de CI/CD pisando versiones** | Correr `gcloud run deploy --set-secrets ...:latest` en la CI/CD sobrescribe la configuración de Terraform. **Mitigación**: CI/CD se limitará a actualizar únicamente la imagen del contenedor (`gcloud run deploy --image ...`), permitiendo que Terraform sea el único dueño de la configuración y de los secretos. |
| **Caracteres especiales en contraseña DB** | Símbolos como `@`, `/` o `:` rompen la estructura de la URL de conexión. **Mitigación**: Utilizar la función nativa `urlencode()` de Terraform sobre la contraseña de la base de datos al compilar la `DATABASE_URL`. |

---

## 4. Fase de Preparación (Bootstrap)

La inicialización se automatizará a través de `scripts/bootstrap.py`:
1. El script lee el proyecto GCP del archivo `.env`.
2. Llama a la API de GCP para verificar si existe el bucket `[PROJECT_ID]-tf-state`.
3. Si no existe, lo crea con Versionado habilitado y bloqueo de acceso público.
4. Ejecuta `terraform init -backend-config="bucket=[PROJECT_ID]-tf-state"` para configurar el backend remoto de forma dinámica.

---

## 5. Tareas Detalladas de Implementación

### - [x] Tarea 1: Crear el Script de Bootstrap de GCP en Python (`scripts/bootstrap.py`)
- **Objetivo**: Automatizar de manera idempotente la creación del bucket de estado, parsear de forma robusta el archivo `.env` local para generar el archivo `terraform/terraform.tfvars.json`, e inicializar el backend remoto de Terraform.
- **Archivos a Crear/Modificar**:
  - `scripts/bootstrap.py`: Crear el script de Python que realice:
    - Leer el archivo `.env` local de forma robusta para obtener `GCP_PROJECT_ID`, `GCP_REGION`, y las credenciales/secretos de la aplicación.
    - Generar un archivo temporal e ignorado por git `terraform/terraform.tfvars.json` mapeando las claves del `.env` directamente a las variables de Terraform (ej. `google_client_secret`, `secret_key`, `mp_access_token`, `db_password`).
    - Usar comandos de `gcloud` (mediante módulo `subprocess`) para comprobar si el bucket `gs://{GCP_PROJECT_ID}-tf-state` existe.
    - Si no existe, ejecutar `gcloud storage buckets create gs://{GCP_PROJECT_ID}-tf-state --project={GCP_PROJECT_ID} --location={GCP_REGION}`.
    - Habilitar versionado en el bucket: `gcloud storage buckets update gs://{GCP_PROJECT_ID}-tf-state --versioning`.
    - Habilitar prevención de acceso público: `gcloud storage buckets update gs://{GCP_PROJECT_ID}-tf-state --public-access-prevention`.
    - Ejecutar `terraform init -backend-config="bucket={GCP_PROJECT_ID}-tf-state"` dentro del directorio `terraform/`.
- **QA / Verificación**:
  - Ejecutar el script localmente con `python scripts/bootstrap.py`.
  - Verificar que el bucket se cree con las especificaciones de seguridad correctas y que se autogenere el archivo `terraform/terraform.tfvars.json` de forma limpia.
  - Asegurar que `.gitignore` incluya `terraform.tfvars.json` para evitar subir secretos a Git.

### - [x] Tarea 2: Configurar Providers y Variables Sensibles en Terraform
- **Objetivo**: Habilitar inicialización de backend parcial y declarar variables sensibles para el aprovisionamiento de secretos en GCP.
- **Archivos a Crear/Modificar**:
  - `terraform/providers.tf`: Modificar la declaración del backend GCS para remover el bucket hardcodeado:
    ```hcl
    terraform {
      backend "gcs" {
        prefix = "terraform/state"
      }
    }
    ```
  - `terraform/variables.tf`: Declarar variables sensibles y tipadas para los secretos de la app (que serán provistas automáticamente por `tfvars.json` localmente o por variables de entorno `TF_VAR_*` en CI/CD):
    ```hcl
    variable "google_client_secret" {
      type      = string
      sensitive = true
    }
    variable "secret_key" {
      type      = string
      sensitive = true
    }
    variable "mp_access_token" {
      type      = string
      sensitive = true
    }
    ```
- **QA / Verificación**:
  - Ejecutar `terraform validate` en el directorio de Terraform y asegurar que no haya errores de validación de sintaxis.

### - [x] Tarea 3: Implementar Inyección Declarativa de Secretos y Control de Despliegue en Cloud Run
- **Objetivo**: Generar de forma declarativa las versiones de secretos en Secret Manager usando las variables provistas, compilar la `DATABASE_URL` dinámica de producción, y asociarlas a Cloud Run protegiendo el ciclo de vida de la imagen del contenedor.
- **Archivos a Crear/Modificar**:
  - `terraform/main.tf`:
    - Añadir bloque `locals` para compilar dinámicamente la `DATABASE_URL` codificando la contraseña:
      ```hcl
      locals {
        database_url = "postgresql://${var.db_user}:${urlencode(var.db_password)}@/${var.db_name}?host=/cloudsql/${google_sql_database_instance.postgres.connection_name}"
      }
      ```
    - Crear recursos `google_secret_manager_secret_version` para inyectar automáticamente los valores:
      ```hcl
      resource "google_secret_manager_secret_version" "secret_versions" {
        for_each = {
          "GOOGLE_CLIENT_SECRET" = var.google_client_secret
          "SECRET_KEY"           = var.secret_key
          "MP_ACCESS_TOKEN"      = var.mp_access_token
          "DATABASE_URL"         = local.database_url
        }
        secret      = google_secret_manager_secret.secrets[each.key].id
        secret_data = each.value
      }
      ```
    - En el bloque `google_cloud_run_v2_service.app`, actualizar el mapeo dinámico de secretos para usar la versión específica creada por Terraform en lugar de `latest`:
      ```hcl
      dynamic "env" {
        for_each = toset(["GOOGLE_CLIENT_SECRET", "SECRET_KEY", "MP_ACCESS_TOKEN", "DATABASE_URL"])
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.secrets[env.key].secret_id
              version = google_secret_manager_secret_version.secret_versions[env.key].version
            }
          }
        }
      }
      ```
    - Añadir el bloque `lifecycle` para prevenir conflictos con los despliegues de la imagen del contenedor desde CI/CD:
      ```hcl
      lifecycle {
        ignore_changes = [
          template[0].containers[0].image
        ]
      }
      ```
- **QA / Verificación**:
  - Ejecutar `terraform plan`. Validar que Terraform planee crear los 4 recursos de `google_secret_manager_secret_version` mapeando sus valores reales de forma correcta.
  - Asegurar que Cloud Run configure la referencia de secreto inmutable apuntando al ID de versión exacto en lugar de "latest".

### - [x] Tarea 4: Refactorizar Despliegue de CI/CD y Script de PowerShell
- **Objetivo**: Prevenir que los despliegues de contenedores sobrescriban o reviertan la asignación de versiones de secretos declarada en Terraform.
- **Archivos a Crear/Modificar**:
  - `deploy_to_gcp.ps1`: Modificar el comando final de despliegue para omitir el parámetro `--set-secrets`. Terraform ya gestiona las conexiones y secretos de forma estricta. El comando de despliegue sólo debe actualizar la imagen del contenedor si se ejecuta fuera de Terraform.
  - `.github/workflows/deploy.yml`: Actualizar el paso `Deploy to Cloud Run` para remover o simplificar parámetros redundantes, asegurando que la acción de GitHub sólo actualice la imagen y preserve las variables y secretos definidos en la plantilla de Terraform.
- **QA / Verificación**:
  - Ejecutar un despliegue de prueba y verificar en la consola de Google Cloud Run que la nueva revisión mantenga la inyección de secretos apuntando a las versiones específicas creadas por Terraform.

---

## Final Verification Wave

### Criterios de Aceptación Técnicos
- **Verificación Bootstrap**: Ejecutar `python scripts/bootstrap.py` crea de manera exitosa el bucket con cifrado, versionado y prevención de acceso público, e inicializa Terraform sin errores.
- **Verificación Declarativa**: Al ejecutar `terraform apply`, los secretos se crean y se inyectan sus valores del `.env` en Secret Manager de forma 100% automatizada. No se requiere ninguna acción manual de copiar y pegar secretos.
- **Verificación de Despliegue**: Cloud Run se despliega correctamente, monta los secretos con sus versiones fijas correspondientes y se conecta a Cloud SQL utilizando la `DATABASE_URL` autogenerada.
- **Verificación CI/CD**: El pipeline en GitHub Actions compila y actualiza la revisión de Cloud Run de forma inmutable sin alterar la gestión de secretos de Terraform.

### Firma del Usuario
El implementador no marcará este plan como completado sin el consentimiento del usuario tras una demostración exitosa de un aprovisionamiento desde cero con el script de bootstrap.
