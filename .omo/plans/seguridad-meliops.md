# Plan de Trabajo: Auditoría y Refactorización de Seguridad para MeliOps (ML Etiquetas)

## 📌 Resumen Ejecutivo
Este plan de trabajo detalla las acciones correctivas necesarias para mitigar cinco (5) vulnerabilidades críticas de seguridad identificadas en el sistema "ML Etiquetas" (MeliOps), optimizando el manejo de sesiones, validación de webhooks de Mercado Pago, protección contra Denegación de Servicio (DoS) y endurecimiento del contenedor Docker.

---

## 🎯 Alcance del Proyecto

### En Alcance (IN)
1. **Remoción de Fallbacks Inseguros**: Asegurar que la aplicación falle inmediatamente si no se carga `SECRET_KEY` en producción.
2. **Seguridad de Sesiones (Cookies)**: Configuración de atributos `secure` e `https_only` en el middleware de sesión de Starlette.
3. **Validación de Firma del Webhook**: Implementación de verificación HMAC-SHA256 del header `x-signature` provisto por Mercado Pago.
4. **Protección DoS por Carga**: Implementación de un límite de tamaño estricto de 200 KB por archivo PDF en el endpoint `/api/v1/extract`.
5. **Endurecimiento del Contenedor**: Configuración de un usuario no-root (`appuser`) para ejecutar la aplicación dentro del contenedor Docker.
6. **Suite de Pruebas**: Adición de tests unitarios y de integración para validar todas las mitigaciones.

### Fuera de Alcance (OUT)
- Implementación de rate limiting distribuido por IP (ej. Redis/Cloud Armor).
- Modificaciones en la base de datos de cuotas de usuario.
- Encriptación de PDFs en reposo.

---

## 🛡️ Directrices Arquitectónicas y Guardias de Seguridad (Metis Analysis)
1. **Validación de Firma Sin Confianza Ciega**: Se continuará validando el pago contra la API oficial de Mercado Pago *después* de pasar la validación HMAC-SHA256 de firma. Esto proporciona defensa en profundidad.
2. **Casing Correcto de Headers**: Starlette normaliza todos los headers a minúsculas, por lo que la firma debe recuperarse usando `request.headers.get("x-signature")`.
3. **Tolerancia del Timestamp (`ts`)**: Validar que la diferencia entre el timestamp `ts` extraído de la firma (en milisegundos) y el tiempo del servidor sea menor a 5 minutos (300,000 ms) para prevenir ataques de replay.
4. **Prevención OOM en Cargas**: El tamaño del archivo se validará antes de realizar cualquier operación de guardado en disco en `/extract` leyendo el tamaño directo mediante `file.file.seek(0, 2)` y `tell()`.

---

## 🛠️ Tareas de Implementación

### Tarea 1: Endurecimiento de Seguridad de Sesión y Claves
- **Archivos a modificar**: `app/main.py`
- **Cambios**:
  - Recuperar `SECRET_KEY` del entorno. Si está vacía o coincide con el fallback estático, lanzar un error crítico (`RuntimeError`) al arrancar para evitar despliegues inseguros.
  - Modificar la inicialización del middleware de sesión para forzar cookies seguras:
    ```python
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key or secret_key == "una_clave_secreta_de_respaldo":
        raise RuntimeError("CRITICAL: SECRET_KEY env var is not set or is insecure!")
    
    app.add_middleware(
        SessionMiddleware,
        secret_key=secret_key,
        https_only=True, # Solo transmitir cookies sobre HTTPS (producción)
        same_site="lax"  # Protección estándar contra CSRF
    )
    ```
- **Escenarios de Verificación (QA)**:
  - Levantar la aplicación localmente sin definir `SECRET_KEY` en el archivo `.env`. Confirmar que el proceso termina con un error explícito.
  - Levantar con `SECRET_KEY` válida y verificar en las herramientas de desarrollo del navegador que la cookie de sesión tiene el atributo `Secure` e `HttpOnly` activo al acceder por HTTPS.

### Tarea 2: Validación de Límite de Tamaño de PDF (200 KB)
- **Archivos a modificar**: `app/api/v1/router_extract.py`
- **Cambios**:
  - En la ruta `/extract`, iterar sobre los archivos cargados (`valid_files`).
  - Obtener el tamaño de cada archivo de manera eficiente sin cargar todo a memoria:
    ```python
    MAX_FILE_SIZE = 204800  # 200 KB en bytes
    
    for file in valid_files:
        # Obtener tamaño
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)  # Resetear puntero
        
        if size > MAX_FILE_SIZE:
            return JSONResponse(
                status_code=400,
                content={"error": f"El archivo '{file.filename}' excede el límite de 200 KB."}
            )
    ```
- **Escenarios de Verificación (QA)**:
  - Intentar subir un PDF legítimo de 250 KB mediante un cliente HTTP (ej. Postman/cURL) o la UI. Verificar código `400 Bad Request` y mensaje descriptivo.
  - Subir un PDF de 150 KB. Confirmar que se procesa exitosamente sin restricciones.

### Tarea 3: Validación de Firma de Webhook de Mercado Pago (HMAC-SHA256)
- **Archivos a modificar**: `app/api/v1/payments.py`
- **Cambios**:
  - Cargar `MP_WEBHOOK_SECRET` usando `os.getenv`.
  - Crear una función auxiliar `verify_webhook_signature(request: Request, body_bytes: bytes) -> bool`.
  - Extraer `x-signature` del header. Separar por comas para obtener el timestamp `ts` y la firma encriptada `v1`.
  - Validar diferencias de tiempo de `ts` para mitigar ataques de repetición.
  - Obtener el parámetro `data.id` de los query params (si existe, convertirlo a minúsculas).
  - Obtener el header `x-request-id`.
  - Construir el template de manifiesto: `id:[data.id_lowercase];request-id:[x-request-id];ts:[ts];` (omitir parámetros si faltan).
  - Calcular HMAC-SHA256 del manifiesto usando la clave `MP_WEBHOOK_SECRET`.
  - Comparar de forma segura contra la firma `v1`.
- **Escenarios de Verificación (QA)**:
  - Enviar un request POST al webhook sin cabecera de firma o con firma corrupta. Verificar que se retorna un código HTTP 400/401 y se ignora el payload.
  - Enviar una notificación firmada correctamente. Confirmar que pasa la validación de firma y ejecuta la lógica de verificación secundaria (GET a `/payments/{id}`).

### Tarea 4: Endurecimiento de Contenedor Docker (No-Root)
- **Archivos a modificar**: `Dockerfile`
- **Cambios**:
  - Crear un usuario y grupo no privilegiados en el contenedor (`appuser` con UID 1000).
  - Ajustar permisos en el directorio `/app` para que pertenezca a `appuser`.
  - Añadir instrucción `USER appuser` antes de exponer el puerto y declarar el comando de ejecución `CMD`.
- **Escenarios de Verificación (QA)**:
  - Construir la imagen localmente: `docker build -t ml-etiquetas .`.
  - Ejecutar un contenedor de prueba y correr un comando para comprobar el ID del usuario: `docker run --rm ml-etiquetas whoami`. Debe retornar `appuser`.

### Tarea 5: Suite de Pruebas de Seguridad
- **Archivos a modificar**: `tests/test_payments.py` (y opcionalmente crear `tests/test_security.py`)
- **Cambios**:
  - Agregar tests para verificar que el webhook valida correctamente las firmas válidas, rechaza las inválidas y maneja la ausencia de firma.
  - Agregar test que intente subir archivos de más de 200 KB a la ruta de extracción y valide el rechazo.
- **Escenarios de Verificación (QA)**:
  - Ejecutar `pytest` y asegurar que la cobertura de la lógica de seguridad y el webhook es del 100%.

---

## 🏁 Final Verification Wave
La verificación final de este plan requiere la ejecución exitosa de la suite de pruebas completa y la aprobación explícita de los resultados por parte del usuario.

### Criterios de Aceptación Globales
1. [x] Todos los tests de regresión y nuevos tests de seguridad pasan sin errores (`pytest`).
2. [x] El contenedor se construye correctamente y se verifica que corre como el usuario `appuser` (ID `1000`).
3. [x] Al levantar la aplicación localmente sin `SECRET_KEY` en el entorno, se produce un error crítico y la app no inicia.
4. [x] Al subir un PDF de más de 200 KB, el endpoint `/extract` retorna un código `413 Request Entity Too Large` o `400 Bad Request` claro de inmediato.
5. [x] El webhook responde `200 OK` para firmas válidas y `400 Bad Request` o `401 Unauthorized` para firmas inválidas o ausentes.
