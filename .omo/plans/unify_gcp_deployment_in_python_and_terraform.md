# Plan de Trabajo: Unificación de Despliegue GCP en Python y Terraform

## 1. Resumen y Objetivos

Este plan tiene como objetivo unificar completamente el ciclo de vida del aprovisionamiento, la compilación de imágenes y el despliegue en GCP dentro de un orquestador multiplataforma en Python (`scripts/bootstrap.py`) y configuraciones de Terraform 100% declarativas. Esto elimina definitivamente todos los scripts de PowerShell (`deploy_to_gcp.ps1` y `undeploy_from_gcp.ps1`), logrando un despliegue inmutable e independiente de la plataforma donde Terraform toma el control absoluto de la versión de la imagen en Cloud Run.

### Criterios de Éxito
- Se eliminan por completo los scripts `.ps1` obsoletos del repositorio.
- `scripts/bootstrap.py` es el único orquestador local para aprovisionamiento, compilación y despliegue continuo en GCP, soportando tanto creación desde cero como destrucción (`--destroy`).
- Terraform gestiona de forma declarativa la etiqueta de imagen del contenedor de Cloud Run (`image_tag`), eliminando el bloque `ignore_changes` para la imagen.
- El script de Python gestiona de manera inteligente el tag de la imagen, extrayendo el Git Commit SHA de forma dinámica y añadiendo un sufijo `-dirty` si el repositorio local tiene cambios sin confirmar.
- `cloudbuild.yaml` se parametriza mediante variables de sustitución de GCP para ser reutilizable y dinámico.
- El pipeline de GitHub Actions se simplifica para usar Terraform para desplegar de forma declarativa el nuevo tag de la imagen de forma consistente con el despliegue local.

---

## 2. Arquitectura y Alcance

### En Alcance (IN)
- **`terraform/variables.tf`**: Declarar la variable `image_tag` con valor predeterminado `"latest"`.
- **`terraform/main.tf`**:
  - Modificar el recurso `google_cloud_run_v2_service.app` para resolver dinámicamente la URL de la imagen usando `image_tag`.
  - Eliminar `template[0].containers[0].image` de la lista de `ignore_changes` en el bloque `lifecycle`.
- **`cloudbuild.yaml`**: Parametrizar con variables de sustitución para `_REGION`, `_REPO_NAME`, e `_IMAGE_TAG` y empujar tanto la etiqueta inmutable como `latest` (para caché).
- **`scripts/bootstrap.py`**: Reescribir para gestionar de forma secuencial y robusta el bootstrap, compilación de imagen, generación de `tfvars.json` y despliegue declarativo de Terraform. Soportar también la flag `--destroy` para la destrucción completa de la infraestructura.
- **`.github/workflows/deploy.yml`**: Refactorizar para compilar la imagen y desplegar a través de Terraform declarativo usando secretos de GitHub mapeados a `TF_VAR_*`.
- **`README.md`**: Actualizar para documentar los nuevos comandos unificados en Python.

### Fuera de Alcance (OUT)
- Modificaciones en la lógica de backend de la aplicación FastAPI.
- Migración de la base de datos de producción.

---

## 3. Decisiones Clave y Mitigación de Riesgos

| Riesgo | Decisión Técnica / Mitigación |
| --- | --- |
| **Problema "Huevo y Gallina" del Registro** | Terraform necesita la imagen del contenedor para crear Cloud Run, pero no se puede construir ni subir la imagen hasta que el Artifact Registry sea creado por Terraform. **Mitigación**: `scripts/bootstrap.py` realizará un apply parcial dirigido (`terraform apply -target=google_artifact_registry_repository.repo -auto-approve`) para garantizar la existencia del registro *antes* de iniciar la compilación. |
| **Retraso de propagación de APIs de GCP** | Al habilitar servicios en GCP, el registro puede fallar por un breve retraso en la API. **Mitigación**: Implementar una pausa de retardo de 10 segundos y un ciclo de reintentos en `scripts/bootstrap.py` después de la activación dirigida del repositorio. |
| **Conflictos de Estado entre CI/CD y Local** | Si eliminamos la imagen de `ignore_changes`, los despliegues directos de la CI/CD entrarán en conflicto con el estado local de Terraform. **Mitigación**: Unificar la metodología. GitHub Actions ya no usará `gcloud run deploy`. En su lugar, tras compilar la imagen, ejecutará `terraform apply` pasando la variable `image_tag` a través de los fallbacks tipados. |
| **Trazabilidad de cambios locales sin confirmar** | Compilar cambios locales usando un Git Commit SHA limpio como tag crea desalineación en el historial. **Mitigación**: `scripts/bootstrap.py` validará el estado del repositorio mediante `git status --porcelain`. Si es "dirty", agregará un sufijo `-dirty` y una marca de tiempo al tag de la imagen. |
| **Hardcoding de credenciales en verificación** | El chequeo de autenticación en PowerShell usaba un correo estático. **Mitigación**: Usar `gcloud auth list --filter=status=ACTIVE --format="value(account)"` de forma dinámica para validar el acceso activo de cualquier usuario. |

---

## 4. Fase de Preparación (Bootstrap)

La inicialización y el flujo completo se automatizarán a través del nuevo `scripts/bootstrap.py`:
1. El script lee `.env` (local) o `os.environ` (CI/CD).
2. Obtiene el Git Commit SHA de forma dinámica y añade el sufijo `-dirty` si hay cambios locales sin confirmar para usarlo como `image_tag`.
3. Genera de forma inmediata el archivo `terraform/terraform.tfvars.json` inyectando todos los secretos y variables de entorno, incluyendo la variable `image_tag` calculada.
4. Verifica la autenticación activa de `gcloud`.
5. Comprueba y crea el bucket de estado `gs://[PROJECT_ID]-tf-state` con versión y seguridad habilitada.
6. Inicializa Terraform dinámicamente usando el bucket creado.
7. Ejecuta apply dirigido del repositorio de Artifact Registry: `terraform apply -target=google_artifact_registry_repository.repo -auto-approve`.
8. Compila y empuja la imagen Docker vía GCP Cloud Build con substitutions del Git SHA dinámico.
9. Ejecuta el apply completo final `terraform apply -auto-approve`.

---

## 5. Tareas Detalladas de Implementación

### Tarea 1: Actualizar Variables y Configuración Declarativa en Terraform
- **Objetivo**: Declarar la variable de imagen y configurar Cloud Run para desplegar de forma declarativa eliminando las excepciones de ciclo de vida.
- **Archivos a Crear/Modificar**:
  - `terraform/variables.tf`: Declarar la variable `image_tag`:
    ```hcl
    variable "image_tag" {
      type        = string
      description = "The container image tag to deploy"
      default     = "latest"
    }
    ```
  - `terraform/main.tf`:
    - En el recurso `google_cloud_run_v2_service.app`, modificar el parámetro `image` para que use la URL de Artifact Registry de forma dinámica:
      ```hcl
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.repo_name}/app:${var.image_tag}"
      ```
    - Modificar el bloque `lifecycle` para eliminar la excepción de imagen:
      ```hcl
      lifecycle {
        # Permitir que Terraform gestione de forma declarativa los cambios en la imagen
        ignore_changes = []
      }
      ```
- **QA / Verificación**:
  - Ejecutar `terraform validate` en el directorio `terraform/` para comprobar que la sintaxis de las variables y del servicio es correcta.

### Tarea 2: Parametrizar y Optimizar `cloudbuild.yaml`
- **Objetivo**: Hacer que la compilación de la imagen en GCP sea dinámica y admita variables de sustitución del tag del contenedor.
- **Archivos a Crear/Modificar**:
  - `cloudbuild.yaml`: Modificar el archivo de pasos de compilación para usar sustituciones:
    ```yaml
    steps:
    - name: 'gcr.io/cloud-builders/docker'
      entrypoint: 'bash'
      args:
      - '-c'
      - |
        docker pull ${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPO_NAME}/app:latest || true
        docker build --cache-from ${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPO_NAME}/app:latest -t ${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPO_NAME}/app:${_IMAGE_TAG} -t ${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPO_NAME}/app:latest .
      env:
        - 'DOCKER_BUILDKIT=1'
    images:
    - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPO_NAME}/app:${_IMAGE_TAG}'
    - '${_REGION}-docker.pkg.dev/${PROJECT_ID}/${_REPO_NAME}/app:latest'
    substitutions:
      _REPO_NAME: 'ml-etiquetas-repo'
      _IMAGE_TAG: 'latest'
      _REGION: 'us-central1'
    ```
- **QA / Verificación**:
  - Verificar la validez de la sintaxis del YAML y comprobar que se definan de forma correcta los valores de default en la sección `substitutions`.

### Tarea 3: Implementar la Orquestación Completa en `scripts/bootstrap.py`
- **Objetivo**: Reescribir el script de bootstrap en Python para soportar el flujo completo de aprovisionamiento, compilación administrada por Git SHA y despliegue declarativo de Terraform.
- **Archivos a Crear/Modificar**:
  - `scripts/bootstrap.py`: Reescribir el archivo de Python para:
    - Soportar el argumento `--destroy` para ejecutar `terraform destroy -auto-approve` si el usuario desea desmantelar el entorno.
    - Autodetectar dinámicamente la cuenta autenticada de GCP con `gcloud auth list`. Si no hay cuenta activa, alertar al usuario para que ejecute `gcloud auth login`.
    - Leer `.env` local y dar soporte fallback automático de lectura de variables desde `os.environ` si el archivo no existe (para CI/CD).
    - Obtener el Git Commit SHA de forma dinámica ejecutando `git rev-parse --short HEAD`.
    - Chequear el estado del repositorio mediante `git status --porcelain`. Si es dirty (contiene cambios sin confirmar), añadir el sufijo `-dirty-{timestamp}` al tag de la imagen.
    - **Escribir de forma inmediata** todas las variables de entorno recopiladas más la variable `image_tag` calculada en el archivo temporal `terraform/terraform.tfvars.json` para que esté disponible en los pasos siguientes.
    - Ejecutar targeted apply de Terraform para crear primero el repositorio de Artifact Registry y esperar 10 segundos para mitigar demoras de GCP: `terraform apply -target=google_artifact_registry_repository.repo -auto-approve`.
    - Trigger de compilación en GCP: `gcloud builds submit --config cloudbuild.yaml --project {project_id} --substitutions=_IMAGE_TAG={image_tag},_REGION={region},_REPO_NAME={repo_name} .`.
    - Ejecutar el apply completo final `terraform apply -auto-approve`.
- **QA / Verificación**:
  - Ejecutar `python scripts/bootstrap.py --dry-run` localmente y verificar que el flujo secuencial y los comandos generados en el stdout sean exactamente los esperados (incluyendo la resolución dinámica del Git SHA, dirty check y substitutions de Cloud Build).

### Tarea 4: Eliminar Scripts de PowerShell y Refactorizar CI/CD (GitHub Actions)
- **Objetivo**: Eliminar definitivamente los scripts `.ps1` obsoletos e integrar el despliegue declarativo inmutable en GitHub Actions.
- **Archivos a Crear/Modificar**:
  - `deploy_to_gcp.ps1`: Eliminar el archivo del repositorio.
  - `undeploy_from_gcp.ps1`: Eliminar el archivo del repositorio.
  - `.github/workflows/deploy.yml`:
    - Eliminar el paso obsoleto `Deploy to Cloud Run (Image Only)` que usa la acción `google-github-actions/deploy-cloudrun`.
    - Instalar Terraform en el runner de GitHub Actions.
    - Ejecutar `terraform init -backend-config="bucket=${{ secrets.GCP_PROJECT_ID }}-tf-state"` dentro de la carpeta `terraform/`.
    - Ejecutar el despliegue a través de Terraform declarativo usando los fallbacks de secretos mapeados en el pipeline:
      ```yaml
      - name: Terraform Apply (Declarative Deploy)
        env:
          TF_VAR_project_id: ${{ secrets.GCP_PROJECT_ID }}
          TF_VAR_region: ${{ secrets.GCP_REGION }}
          TF_VAR_google_client_id: ${{ secrets.GOOGLE_CLIENT_ID }}
          TF_VAR_google_client_secret: ${{ secrets.GOOGLE_CLIENT_SECRET }}
          TF_VAR_secret_key: ${{ secrets.SECRET_KEY }}
          TF_VAR_mp_access_token: ${{ secrets.MP_ACCESS_TOKEN }}
          TF_VAR_db_password: ${{ secrets.DB_PASSWORD }}
        run: |
          terraform apply -auto-approve -var="image_tag=${{ github.sha }}"
        working-directory: terraform
      ```
  - `README.md`: Actualizar la documentación para remover las referencias a los scripts de PowerShell y reemplazarlas con las instrucciones de uso unificadas de `scripts/bootstrap.py` (ej. `python scripts/bootstrap.py` para despliegue y `python scripts/bootstrap.py --destroy` para desmontar).
- **QA / Verificación**:
  - Verificar que no queden llamadas a `.ps1` en ninguna parte del repositorio ni en workflows.
  - Asegurar que el pipeline de GitHub Actions valide de forma correcta el despliegue declarativo pasando la variable `image_tag`.

---

## Final Verification Wave

### Criterios de Aceptación Técnicos
- **Verificación de Orquestador Local**: Ejecutar `python scripts/bootstrap.py` desde cero automatiza de forma limpia la creación del bucket, la compilación de la imagen usando el Git SHA con soporte de dirty status, escribe el archivo `terraform.tfvars.json` y completa el apply declarativo en Cloud Run sin intervenciones manuales.
- **Verificación de Destrucción**: Ejecutar `python scripts/bootstrap.py --destroy` remueve de forma atómica y completa la infraestructura en GCP usando Terraform.
- **Verificación CI/CD**: Un push a la rama principal gatilla el workflow de GitHub Actions, que compila la imagen de forma autenticada usando el caché GHA y despliega a través de Terraform declarativo sin causar conflictos de estado ni reversiones indeseadas de imágenes.
- **Verificación de Ausencia**: No queda ningún archivo `.ps1` ni comando de despliegue directo de Cloud Run imperativo (`gcloud run deploy`) en la suite de integración.

### Firma del Usuario
El implementador no marcará este plan como completado sin el consentimiento explícito del usuario tras comprobar el pipeline de CI/CD de GitHub Actions finalizado con éxito de forma declarativa.
