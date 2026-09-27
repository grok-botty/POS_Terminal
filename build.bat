@echo off
echo 🔨 Начинаем сборку CashMachine...

REM Шаг 1: Сборка фронтенда
echo.
echo 📦 Шаг 1/3: Сборка React фронтенда...
cd frontend
call npm install
call npm run build
cd ..

REM Шаг 2: Копирование dist в backend
echo.
echo 📋 Шаг 2/3: Копирование frontend в backend...
if exist backend\app\dist rmdir /s /q backend\app\dist
xcopy /E /I /Y frontend\dist backend\app\dist

REM Шаг 3: Сборка с PyInstaller
echo.
echo 🎁 Шаг 3/3: Упаковка с PyInstaller...
pyinstaller build.spec --clean

echo.
echo ✅ Сборка завершена!
echo 📦 Исполняемый файл: dist\CashMachine.exe
echo.
echo Для запуска:
echo   dist\CashMachine.exe
pause
