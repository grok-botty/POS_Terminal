# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the CashMachine Windows/desktop bundle.

Build from the repository root:

    pyinstaller --clean --noconfirm desktop/pyinstaller_spec.spec

The output binary is written to ``dist/CashMachine[.exe]``.

Run ``manage.py collectstatic`` first so ``staticfiles/`` can be bundled for
WhiteNoise. The spec also collects first-party apps (Django imports them by
name) and pywebview.
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
)

PROJECT_ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 - SPECPATH provided by PyInstaller

sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault(
    "CASHMACHINE_DB_PATH",
    str(PROJECT_ROOT / "build" / "pyinstaller-spec.sqlite3"),
)
os.environ.setdefault("CASHMACHINE_DEBUG", "0")

import django  # noqa: E402

django.setup()


def _bundle_module(name: str) -> bool:
    """Skip test modules; they are not needed in the cashier-facing exe."""
    return ".tests" not in name and not name.endswith(".tests")


datas = []
binaries = []
datas += [(str(PROJECT_ROOT / "config"), "config")]
datas += [(str(PROJECT_ROOT / "apps"), "apps")]
datas += [(str(PROJECT_ROOT / "templates"), "templates")]
datas += [(str(PROJECT_ROOT / "static"), "static")]

_collected_static = PROJECT_ROOT / "staticfiles"
if _collected_static.is_dir():
    datas += [(str(_collected_static), "staticfiles")]

# Django ships templates & static files inside its package tree.
datas += collect_data_files("django", includes=["**/templates/*", "**/static/*"])
datas += collect_data_files("django_htmx")


hiddenimports = []
hiddenimports += collect_submodules("django")
hiddenimports += collect_submodules("django_htmx")
hiddenimports += collect_submodules("whitenoise")
hiddenimports += collect_submodules("apps", filter=_bundle_module, on_error="ignore")
hiddenimports += collect_submodules("config", filter=_bundle_module, on_error="ignore")
hiddenimports += [
    "apps.accounts",
    "apps.accounts.migrations",
    "apps.catalog",
    "apps.catalog.migrations",
    "apps.orders",
    "apps.orders.migrations",
    "apps.analytics",
    "apps.analytics.migrations",
    "apps.pos",
    "apps.pos.migrations",
    "config",
    "config.settings",
    "config.urls",
    "config.wsgi",
]

# pywebview is imported inside a function, so trace it explicitly. GUI
# backends that are not installed on this machine are ignored.
for _pkg in ("webview",):
    try:
        _d, _b, _h = collect_all(_pkg, on_error="ignore")
    except Exception:
        continue
    datas += _d
    binaries += _b
    hiddenimports += _h


a = Analysis(
    [str(PROJECT_ROOT / "desktop" / "launcher.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(PROJECT_ROOT / "desktop" / "pyi_rth_django_path.py")],
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CashMachine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
