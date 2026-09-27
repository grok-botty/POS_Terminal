#!/bin/bash
set -e

echo "🔨 Начинаем сборку CashMachine..."

# Шаг 1: Сборка фронтенда
echo ""
echo "📦 Шаг 1/3: Сборка React фронтенда..."
cd frontend
npm install
npm run build
cd ..

# Шаг 2: Копирование dist в backend
echo ""
echo "📋 Шаг 2/3: Копирование frontend в backend..."
rm -rf backend/app/dist
cp -r frontend/dist backend/app/dist

# Шаг 3: Сборка с PyInstaller
echo ""
echo "🎁 Шаг 3/3: Упаковка с PyInstaller..."
pyinstaller build.spec --clean

echo ""
echo "✅ Сборка завершена!"
echo "📦 Исполняемый файл: dist/CashMachine"
echo ""
echo "Для запуска:"
echo "  ./dist/CashMachine"
