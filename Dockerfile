FROM python:3.12-slim

# Establecer el directorio de trabajo
WORKDIR /app

# Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalar uv para una gestión rápida de dependencias
RUN pip install --no-cache-dir uv

# Copiar archivos de configuración de dependencias
COPY pyproject.toml uv.lock ./

# Instalar las dependencias usando uv
RUN uv sync --frozen --no-dev

# Añadir el entorno virtual al PATH
ENV PATH="/app/.venv/bin:$PATH"

# Copiar el resto del código de la aplicación
COPY . .

# Exponer el puerto en el que corre la aplicación
EXPOSE 8080

# Comando para iniciar la aplicación
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
