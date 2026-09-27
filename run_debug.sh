#!/bin/bash

# Скрипт для быстрого запуска в режиме дебага
# Собирает фронтенд, копирует в backend и запускает сервер

set -e  # Останавливаться при ошибках

echo "🚀 Запуск в режиме дебага..."
echo ""

# Переходим в директорию frontend
echo "📦 Сборка фронтенда..."
cd frontend

# Устанавливаем зависимости если нужно
if [ ! -d "node_modules" ]; then
    echo "📥 Установка зависимостей..."
    npm install
fi

# Собираем фронтенд
echo "🔨 Компиляция фронтенда..."
npm run build

# Возвращаемся в корень
cd ..

# Копируем собранный фронтенд в backend
echo "📋 Копирование фронтенда в backend..."
rm -rf backend/app/dist
cp -r frontend/dist backend/app/dist

echo "✅ Фронтенд собран и скопирован"
echo ""

# Проверяем виртуальное окружение Python
if [ ! -d ".venv" ]; then
    echo "⚠️  Виртуальное окружение не найдено"
    echo "Создаём виртуальное окружение..."
    python3 -m venv .venv
    source .venv/bin/activate
    echo "📥 Установка зависимостей Python..."
    pip install -r requirements-build.txt
else
    source .venv/bin/activate
fi

echo "🐍 Запуск Django сервера..."
echo "📍 Сервер будет доступен по адресу: http://127.0.0.1:8000"
echo ""
echo "Для остановки нажмите Ctrl+C"
echo ""

# Запускаем сервер
cd backend
python launcher.py
