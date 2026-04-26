# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — produces a single-file SyroceKBSAgent.exe.

Build (on Windows):
    pyinstaller installer/SyroceKBSAgent.spec --clean --noconfirm

Output: dist/SyroceKBSAgent.exe

Notes:
  - Bundles the FastAPI + worker code under backend/.
  - icon, version metadata are optional; add `icon='installer/icon.ico'` once
    a real icon is ready.
  - --onefile produces a self-extracting binary (slower first start but a
    single artifact for Inno Setup to ship).
  - We hide most stdlib console windows; tray mode shows a tray icon only.
"""
import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

PROJECT_ROOT = os.path.abspath(os.path.dirname(SPECPATH))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")

hiddenimports = [
    # FastAPI / uvicorn pull these dynamically
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    # Our backend
    *collect_submodules("backend"),
    # Windows-only deps
    "win32timezone",
    "win32serviceutil",
    "win32service",
    "win32event",
    "win32evtlog",
    "win32evtlogutil",
    "win32crypt",
    "servicemanager",
    "pystray",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
]

a = Analysis(
    [os.path.join(BACKEND_DIR, "__main__.py")],
    pathex=[BACKEND_DIR, PROJECT_ROOT],
    binaries=[],
    datas=[
        # Frontend build (if shipped together): uncomment when frontend
        # is bundled into the same exe.
        # (os.path.join(PROJECT_ROOT, "frontend", "build"), "frontend_build"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "numpy", "pandas",  # not used; keep size down
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
    name="SyroceKBSAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI subsystem — tray mode has no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='installer/icon.ico',
)
