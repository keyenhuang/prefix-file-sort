# -*- mode: python ; coding: utf-8 -*-

import sys
import os

block_cipher = None

datas = []

# Hidden imports for tkinterdnd2 and package modules
hiddenimports = ['tkinterdnd2', 'prefix_file_sort']

a = Analysis(
    ['src/prefix_file_sort/main.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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

# Detect icon file if available
icon_file = None
for name in ('app.ico', 'icon.ico', 'prefix_file_sort.ico'):
    if os.path.exists(name):
        icon_file = name
        datas.append((name, '.'))
        break

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='prefix-file-sort',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='prefix-file-sort',
)
