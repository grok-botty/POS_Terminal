# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the CashMachine Windows/desktop bundle.

Build from the repository root:

    pyinstaller --clean --noconfirm desktop/pyinstaller_spec.spec

The output binary is written to ``dist/CashMachine[.exe]``.

The spec collects Django's built-in templates, contrib apps, static files and
all first-party apps/templates so the frozen bundle is self-contained.
"""

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
)

PROJECT_ROOT = Path(SPECPATH).resolve().parent  # noqa: F821 - SPECPATH provided by PyInstaller

datas = []
datas += [(str(PROJECT_ROOT / "config"), "config")]
datas += [(str(PROJECT_ROOT / "apps"), "apps")]
datas += [(str(PROJECT_ROOT / "templates"), "templates")]
datas += [(str(PROJECT_ROOT / "static"), "static")]

# Django ships templates & static files inside its package tree.
datas += collect_data_files("django", includes=["**/templates/*", "**/static/*"])
datas += collect_data_files("django_htmx")


hiddenimports = []
hiddenimports += collect_submodules("django")
hiddenimports += collect_submodules("django_htmx")
hiddenimports += collect_submodules("whitenoise")
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


block_cipher = None


a = Analysis(
    [str(PROJECT_ROOT / "desktop" / "launcher.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
