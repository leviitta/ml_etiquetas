# Plan de Trabajo: Corrección de Subprocess FileNotFoundError en Windows para `bootstrap.py`

## 1. Resumen y Objetivos

Este plan tiene como objetivo corregir el fallo `FileNotFoundError: [WinError 2]` en sistemas Windows al ejecutar `scripts/bootstrap.py`. El error ocurre porque el API `CreateProcess` de Windows no puede resolver scripts de lote o wrappers de consola (como `gcloud.cmd` o `terraform.exe`) del PATH del sistema sin iniciar explícitamente un intérprete de comandos (`cmd.exe`). Se implementará una solución robusta y compatible con múltiples plataformas utilizando el parámetro `shell=True` de manera selectiva, y se añadirán controles pre-flight para validar las dependencias requeridas antes de su ejecución.

### Criterios de Éxito
- El script de Python `scripts/bootstrap.py` se ejecuta con éxito en entornos Windows sin lanzar excepciones de archivo no encontrado al llamar a `gcloud`, `terraform` o `git`.
- Se mantiene la compatibilidad absoluta con entornos Unix/Linux/macOS y pipelines de GitHub Actions.
- El script valida de forma proactiva y amigable que `gcloud`, `terraform` y `git` estén instalados en el sistema antes de iniciar, arrojando errores amigables si falta alguno.

---

## 2. Arquitectura y Alcance

### En Alcance (IN)
- **`scripts/bootstrap.py`**:
  - Importar el módulo `shutil` de la librería estándar de Python.
  - Añadir pre-flight checks con `shutil.which` para `gcloud`, `terraform` y `git`.
  - Configurar `shell=(os.name == 'nt')` en todas las llamadas de `subprocess.run` dentro del script (tanto en `run_command` como en llamadas directas).

### Fuera de Alcance (OUT)
- Modificación de cualquier archivo fuera de `scripts/bootstrap.py`.

---

## 3. Decisiones Clave y Mitigación de Riesgos

| Riesgo | Decisión Técnica / Mitigación |
| --- | --- |
| **Comportamiento silencioso de `shell=True` en fallos** | En Windows, llamar a un comando inexistente con `shell=True` puede fallar de forma silenciosa o retornar códigos de salida inusuales. **Mitigación**: Se implementa un pre-flight check explícito con `shutil.which` antes de ejecutar cualquier comando shell. |
| **Problemas de parsing de argumentos en `cmd.exe`** | `shell=True` en Windows pasa los argumentos a través de la shell, lo que puede requerir quoting adicional. **Mitigación**: Las llamadas en este script usan listas de argumentos seguras y directas que la API de `subprocess` procesa y escapa de forma nativa al invocar el intérprete de Windows. |

---

## 4. Fase de Preparación (Bootstrap)

N/A. Se trata de un hotfix directo en el script de bootstrap.

---

## 5. Tareas Detalladas de Implementación

### Tarea 1: Agregar Pre-flight Checks de Herramientas Requeridas
- **Objetivo**: Asegurar que las herramientas de consola requeridas estén disponibles en el PATH antes de iniciar la orquestación.
- **Archivos a Crear/Modificar**:
  - `scripts/bootstrap.py`:
    - Importar el módulo `shutil` al inicio del archivo.
    - Al inicio de la función `main()`, comprobar la presencia de las herramientas:
      ```python
      required_tools = ["gcloud", "terraform", "git"]
      missing_tools = []
      for tool in required_tools:
          if not shutil.which(tool):
              missing_tools.append(tool)
      if missing_tools:
          print("❌ Error: Faltan las siguientes herramientas requeridas en tu PATH del sistema:")
          for tool in missing_tools:
              print(f"  - {tool}")
          print("\nPor favor, instala las herramientas faltantes y asegúrate de agregarlas a tus variables de entorno.")
          sys.exit(1)
      ```
- **QA / Verificación**:
  - Ejecutar el script localmente con `python scripts/bootstrap.py`.
  - Verificar que si tienes todas las herramientas instaladas, el script continúe con éxito la detección sin mostrar errores de falta de herramientas.

### Tarea 2: Configurar `shell=(os.name == 'nt')` en `run_command`
- **Objetivo**: Asegurar que la función utilitaria `run_command` resuelva los comandos de consola en sistemas Windows a través de la shell de manera dinámica.
- **Archivos a Crear/Modificar**:
  - `scripts/bootstrap.py`:
    - En la función `run_command`, definir una variable `use_shell = os.name == 'nt'`.
    - Pasar el parámetro `shell=use_shell` en ambas ramas de llamadas a `subprocess.run()` (con `capture=True` y `capture=False`).
- **QA / Verificación**:
  - Ejecutar `python scripts/bootstrap.py --dry-run`.
  - Verificar que el script corra correctamente de forma simulada sin levantar excepciones `FileNotFoundError` en Windows.

### Tarea 3: Configurar `shell=(os.name == 'nt')` en Llamadas de `subprocess.run` Directas
- **Objetivo**: Resolver de manera compatible la llamada de subproceso directa en el script que obtiene la firma del Git Commit SHA.
- **Archivos a Crear/Modificar**:
  - `scripts/bootstrap.py`:
    - Identificar la llamada de `subprocess.run` que lee la salida de Git o cualquier comando directo (ej. línea 169 o similar).
    - Añadir `shell=(os.name == 'nt')` al invocar `subprocess.run` para asegurar consistencia en Windows.
- **QA / Verificación**:
  - Asegurar que todas las llamadas de subproceso en el script utilicen el parámetro de shell de forma condicional para Windows.

---

## Final Verification Wave

### Criterios de Aceptación Técnicos
- **Verificación de Ejecución Windows**: Ejecutar `python scripts/bootstrap.py --dry-run` en Windows funciona con éxito y muestra los comandos simulados sin levantar ninguna excepción de archivo no encontrado.
- **Verificación Multiplataforma**: El mismo comando en Linux/WSL/GHA ejecuta la validación y el flujo con éxito, garantizando total compatibilidad entre sistemas operativos.
- **Verificación de Pre-flight**: Si falta alguno de los binarios requeridos (`gcloud`, `terraform` o `git`), el script aborta inmediatamente con un mensaje amigable detallando exactamente qué herramienta falta, en lugar de crashear con un stacktrace de Python.

### Firma del Usuario
El implementador no marcará este plan como completado sin el consentimiento del usuario tras validar una ejecución limpia de `python scripts/bootstrap.py --dry-run` en su máquina Windows.
