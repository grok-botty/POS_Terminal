#!/usr/bin/env bash
# Build a self-contained CashMachine binary for the current platform.
#
# The script is intended for macOS / Linux developer testing of the desktop
# packaging path; the Windows target is built with desktop\build.bat.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-desktop.txt

python manage.py collectstatic --noinput

pyinstaller --clean --noconfirm desktop/pyinstaller_spec.spec

echo
echo "Готово. Бинарник: dist/CashMachine"
