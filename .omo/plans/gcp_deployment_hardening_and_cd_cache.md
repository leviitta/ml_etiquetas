# Plan de Trabajo: Endurecimiento de Permisos GCP y Optimización de Caché en CI/CD

## 1. Resumen y Objetivos

Este plan tiene como objetivo aplicar las recomendaciones surgidas de la auditoría técnica del equipo para robustecer la seguridad y optimizar el rendimiento del pipeline de CI/CD. Se reemplaza el uso de permisos genéricos por un conjunto de roles administrativos granulares bajo el principio de menor privilegio, y se refactoriza el workflow de GitHub Actions para soportar caché de plugins de Terraform, bootstrapping automático de permisos del registro y despliegues deterministas basados en planes estáticos.

### Criterios de Éxito
- El Service Account de despliegue (`ml-etiquetas-deploy-sa`) se configura con los roles administrativos exactos de GCP requeridos para gestionar la infraestructura, incluyendo permisos para vincular políticas de IAM y leer/escribir el estado remoto en GCS.
- Se implementa un sistema de caché de plugins de Terraform en GitHub Actions, reduciendo los tiempos de inicialización (`terraform init`) hasta en un 80%.
- El pipeline de GitHub Actions resuelve la dependencia circular del registro de forma segura, ejecutando un apply dirigido dual del repositorio y de los permisos de escritura del Service Account de despliegue antes de compilar la imagen.
- Se asegura que los despliegues de infraestructura en la CI/CD sean completamente deterministas y transaccionales a través de la separación estricta de `terraform plan -out=tfplan` y `terraform apply tfplan`.
- Se mitiga el riesgo de exposición de secretos en texto plano agregando los planes estáticos (`*.tfplan`) al archivo `.gitignore`.

---

## 2. Arquitectura y Alcance

### En Alcance (IN)
- **`terraform/main.tf`**:
  - Declarar y vincular los roles administrativos específicos para `ml-etiquetas-deploy-sa`.
  - Asegurar la asignación de roles críticos para la gestión de IAM (`roles/resourcemanager.projectIamAdmin`) y el estado de Terraform (`roles/storage.objectAdmin`).
- **`.gitignore`**: Agregar exclusión estricta de archivos de plan estático (`*.tfplan` y `tfplan`).
- **`.github/workflows/deploy.yml`**:
  - Configurar caché de plugins de Terraform usando `actions/cache@v4` y el directorio de caché oficial `TF_PLUGIN_CACHE_DIR`.
  - Reordenar los pasos para inicializar Terraform y aplicar los recursos del repositorio y permisos dirigidos *antes* del paso de compilación Docker.
  - Implementar la separación de `terraform plan` y `terraform apply tfplan`.

### Fuera de Alcance (OUT)
- Modificación de la lógica de backend de la aplicación FastAPI.
- Aprovisionamiento de nuevas bases de datos o recursos no declarados previamente.

---

## 3. Decisiones Clave y Mitigación de Riesgos

| Riesgo | Decisión Técnica / Mitigación |
| --- | --- |
| **Fallo de permisos mid-run en GHA** | El Service Account de despliegue no tiene permisos para aplicar políticas de IAM del proyecto. **Mitigación**: Se otorga explícitamente el rol `roles/resourcemanager.projectIamAdmin` en `terraform/main.tf` para que el Service Account pueda realizar los bindings requeridos. |
| **Pérdida de acceso al Estado de GCS** | Al remover los roles excesivamente amplios (`roles/owner` o `roles/editor`), Terraform no puede leer ni escribir el archivo `terraform.tfstate`. **Mitigación**: Se añade de forma obligatoria el rol `roles/storage.objectAdmin` al Service Account de despliegue en la definición de Terraform. |
| **Error de empuje por falta de permisos** | Si solo se ejecuta un apply dirigido al repositorio Artifact Registry en GHA, la CI/CD fallará en el paso de Docker push por falta de permisos de escritura. **Mitigación**: El apply dirigido debe ser dual, apuntando simultáneamente al repositorio y al binding de permisos de escritura de Artifact Registry: `terraform apply -target=google_artifact_registry_repository.repo -target=google_project_iam_member.sa_ar_writer -auto-approve`. |
| **Exposición de secretos en `tfplan`** | Los archivos de plan estático generados por Terraform contienen secretos sensibles en texto plano. **Mitigación**: Se agrega la exclusión `*.tfplan` y `tfplan` en el archivo `.gitignore` para bloquear de forma segura cualquier subida accidental al repositorio. |
| **Lentitud en descargas de proveedores** | `terraform init` descarga todos los plugins de proveedores en cada ejecución, lo que ralentiza el pipeline. **Mitigación**: Se configura un directorio central de caché en GHA (`~/.terraform.d/plugin-cache`) y se asegura su creación mediante `mkdir -p` antes de correr el init. |

---

## 4. Fase de Preparación (Bootstrap)

Toda la inicialización de la infraestructura local se mantendrá administrada de manera robusta por `scripts/bootstrap.py`. Este plan se enfoca en robustecer y blindar la ejecución del pipeline automatizado en GitHub Actions cuando se gatilla por un push a la rama `main`.

---

## 5. Tareas Detalladas de Implementación

### Tarea 1: Otorgar Roles Administrativos Granulares al Service Account de Despliegue
- **Objetivo**: Configurar de forma declarativa y segura las cuentas de servicio en Terraform bajo el principio de menor privilegio, asegurando la asignación de permisos críticos de IAM y Storage.
- **Archivos a Crear/Modificar**:
  - `terraform/main.tf`: Modificar los recursos de IAM para `google_service_account.deploy_sa` para otorgar los siguientes roles granulares a nivel de proyecto:
    - `roles/artifactregistry.admin`
    - `roles/cloudsql.admin`
    - `roles/secretmanager.admin`
    - `roles/run.admin`
    - `roles/resourcemanager.projectIamAdmin` (Crítico: para que el Service Account pueda declarar bindings de IAM en el proyecto)
    - `roles/serviceusage.serviceUsageAdmin` (Para habilitación de APIs)
    - `roles/iam.serviceAccountAdmin` (Para gestionar Service Accounts)
    - `roles/iam.workloadIdentityPoolAdmin` (Para gestionar WIF)
    - `roles/storage.objectAdmin` (Crítico: para que el Service Account pueda leer y escribir el estado en la cubeta GCS)
    - `roles/iam.serviceAccountUser` (Para vincular cuentas de servicio a Cloud Run)
- **QA / Verificación**:
  - Ejecutar `terraform validate` en el directorio `terraform/` para validar la correcta sintaxis de la declaración de recursos IAM.

### Tarea 2: Ocultar Planes de Terraform (`.gitignore`)
- **Objetivo**: Prevenir la filtración de secretos y datos sensibles de la infraestructura asegurando que los archivos de plan no se guarden en Git.
- **Archivos a Crear/Modificar**:
  - `.gitignore`: Añadir las siguientes líneas al final del archivo:
    ```
    # Terraform Plan
    *.tfplan
    tfplan
    ```
- **QA / Verificación**:
  - Verificar que al ejecutar `git status` no se rastree ningún archivo con extensión `.tfplan`.

### Tarea 3: Implementar Caché de Plugins de Terraform en GitHub Actions
- **Objetivo**: Reducir significativamente el tiempo de ejecución de la CI/CD almacenando y restaurando los binarios de los proveedores de Terraform.
- **Archivos a Crear/Modificar**:
  - `.github/workflows/deploy.yml`:
    - En el job `deploy`, configurar la variable de entorno a nivel de job:
      ```yaml
      env:
        TF_PLUGIN_CACHE_DIR: ${{ github.workspace }}/.terraform.d/plugin-cache
      ```
    - Añadir un paso de caché para los plugins de Terraform antes de configurar Terraform:
      ```yaml
      - name: Cache Terraform plugins
        uses: actions/cache@v4
        with:
          path: ${{ github.workspace }}/.terraform.d/plugin-cache
          key: ${{ runner.os }}-terraform-${{ hashFiles('terraform/.terraform.lock.hcl') }}
      ```
    - En el paso de inicialización, asegurar la creación del directorio de caché antes de ejecutar `terraform init`:
      ```yaml
      - name: Terraform Init
        run: |
          mkdir -p ${{ github.workspace }}/.terraform.d/plugin-cache
          terraform init -backend-config="bucket=${{ secrets.GCP_PROJECT_ID }}-tf-state"
        working-directory: terraform
      ```
- **QA / Verificación**:
  - Ejecutar el workflow y verificar en la sección "Post Cache Terraform plugins" que el caché se guarde de manera correcta para las siguientes ejecuciones.

### Tarea 4: Refactorizar Pasos de Despliegue en GitHub Actions
- **Objetivo**: Configurar un flujo de despliegue determinista y desacoplado de dependencias circulares en GitHub Actions.
- **Archivos a Crear/Modificar**:
  - `.github/workflows/deploy.yml`:
    - Reordenar los pasos de Terraform para que se ejecuten **antes** del paso de compilación Docker.
    - Implementar el targeted apply dual de bootstrap:
      ```yaml
      - name: Terraform Targeted Apply (Registry and IAM)
        env:
          TF_VAR_project_id: ${{ secrets.GCP_PROJECT_ID }}
          TF_VAR_region: ${{ secrets.GCP_REGION }}
          TF_VAR_google_client_id: ${{ secrets.GOOGLE_CLIENT_ID }}
          TF_VAR_google_client_secret: ${{ secrets.GOOGLE_CLIENT_SECRET }}
          TF_VAR_secret_key: ${{ secrets.SECRET_KEY }}
          TF_VAR_mp_access_token: ${{ secrets.MP_ACCESS_TOKEN }}
          TF_VAR_db_password: ${{ secrets.DB_PASSWORD }}
        run: |
          terraform apply -target=google_artifact_registry_repository.repo -target=google_project_iam_member.sa_ar_writer -auto-approve
        working-directory: terraform
      ```
    - Tras el paso de compilación Docker (`docker/build-push-action`), ejecutar el despliegue determinista de Terraform en dos pasos (generando y aplicando el plan estático):
      ```yaml
      - name: Terraform Plan
        env:
          TF_VAR_project_id: ${{ secrets.GCP_PROJECT_ID }}
          TF_VAR_region: ${{ secrets.GCP_REGION }}
          TF_VAR_google_client_id: ${{ secrets.GOOGLE_CLIENT_ID }}
          TF_VAR_google_client_secret: ${{ secrets.GOOGLE_CLIENT_SECRET }}
          TF_VAR_secret_key: ${{ secrets.SECRET_KEY }}
          TF_VAR_mp_access_token: ${{ secrets.MP_ACCESS_TOKEN }}
          TF_VAR_db_password: ${{ secrets.DB_PASSWORD }}
        run: |
          terraform plan -out=tfplan -var="image_tag=${{ github.sha }}"
        working-directory: terraform

      - name: Terraform Apply
        run: |
          terraform apply -auto-approve tfplan
        working-directory: terraform
      ```
- **QA / Verificación**:
  - Monitorear la ejecución del pipeline y asegurar que la compilación de la imagen Docker ocurra de forma exitosa inmediatamente después de que el targeted apply garantice la existencia del Artifact Registry y los permisos de escritura correspondientes.
  - Verificar que el paso final de `terraform apply` use el archivo `tfplan` estático generado previamente.

---

## Final Verification Wave

### Criterios de Aceptación Técnicos
- **Verificación de Permisos**: La ejecución de `terraform apply` en el pipeline de GitHub Actions se ejecuta sin ningún error de "Permission Denied" al administrar IAM u otros recursos de infraestructura en GCP.
- **Verificación de Dependencia**: GHA inicializa de forma exitosa, crea el repositorio, otorga permisos, construye/empuja la imagen, genera el plan estático de forma segura, y finalmente despliega la revisión de Cloud Run de forma declarativa.
- **Verificación de Caché**: Las ejecuciones de GHA muestran un cache hit exitoso para los plugins de Terraform en el paso de restauración de caché, ahorrando descargas innecesarias.
- **Verificación de Seguridad**: Ningún archivo `.tfplan` se guarda ni se muestra en el árbol de cambios del repositorio (`git status`).

### Firma del Usuario
El implementador no marcará este plan como completado sin el consentimiento del usuario tras verificar que una corrida completa de GitHub Actions pase de manera exitosa y declarativa en la rama `main`.
