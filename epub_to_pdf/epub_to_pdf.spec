# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for epub2pdf standalone executable."""

import sys
from pathlib import Path

block_cipher = None

# Determine paths relative to spec file location
spec_root = Path(SPECPATH)
fonts_dir = spec_root / 'fonts'

# Set executable name with platform-specific extension
exe_name = 'epub2pdf.exe' if sys.platform == 'win32' else 'epub2pdf'

a = Analysis(
    ['epub_to_pdf.py'],
    pathex=[],
    binaries=[],
    datas=[
        (str(fonts_dir), 'fonts'),  # Include font files
    ],
    hiddenimports=[
        'pypandoc',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'PIL',
        'tkinter',
        'unittest',
        'pydoc',
    ],
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
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Enable UPX compression
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # CLI application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
