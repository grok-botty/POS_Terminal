FROM python:3.10-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && \
    apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Копирование и установка Python зависимостей
COPY requirements-build.txt .
RUN pip install --no-cache-dir -r requirements-build.txt

# Сборка фронтенда
COPY frontend/package*.json frontend/
WORKDIR /app/frontend
RUN npm ci
COPY frontend/ .
RUN npm run build

# Копирование backend
WORKDIR /app
COPY backend/ backend/

# Копирование собранного фронтенда
RUN cp -r frontend/dist backend/app/dist

# Создание директории для данных
RUN mkdir -p /data

# Переменные окружения
ENV DOCKER_ENV=1
ENV HOST=0.0.0.0
ENV PORT=8080

EXPOSE 8080

CMD ["python", "backend/launcher.py"]
