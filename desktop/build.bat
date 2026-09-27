@echo off
REM Build a single-file Windows .exe for CashMachine.
REM
REM Usage (from the repository root, in an activated venv):
REM     desktop\build.bat
REM
REM Produces dist\CashMachine.exe.

setlocal
set ROOT=%~dp0..
cd /d "%ROOT%"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-desktop.txt

REM Collect static files so WhiteNoise can serve them from within the bundle.
python manage.py collectstatic --noinput

pyinstaller --clean --noconfirm desktop\pyinstaller_spec.spec

echo.
echo Готово. Исполняемый файл: dist\CashMachine.exe
endlocal
