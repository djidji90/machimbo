# 1. Imagen base de Python
FROM python:3.12-slim

# 2. Evitar creación de archivos .pyc y salida buffer
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Directorio de trabajo dentro del contenedor
WORKDIR /app

# 4. Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# 5. Copiar requirements e instalar dependencias
COPY djidji1/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiar todo el código
COPY djidji1/ .

# 7. Crear carpetas para archivos estáticos y media
RUN mkdir -p /app/media /app/static

# 8. Comando por defecto para producción
CMD ["gunicorn", "djidji1.wsgi:application", "--bind", "0.0.0.0:8000"]
