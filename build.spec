# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['backend/launcher.py'],
    pathex=['backend'],
    binaries=[],
    datas=[
        ('backend/app/dist', 'app/dist'),
        ('backend/app/__init__.py', 'app'),
        ('backend/__init__.py', '.'),
    ],
    hiddenimports=[
        'django',
        'django.contrib.contenttypes',
        'django.contrib.staticfiles',
        'django.core.management',
        'django.core.management.commands',
        'django.core.management.commands.runserver',
        'django.core.management.commands.migrate',
        'django.db.backends.sqlite3',
        'corsheaders',
        'corsheaders.middleware',
        'google.oauth2.service_account',
        'googleapiclient.discovery',
        'googleapiclient.http',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CashMachine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Включаем консоль для отладки
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Можно добавить путь к .ico файлу
)
