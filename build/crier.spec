# PyInstaller spec for Crier. Build with:  pyinstaller build/crier.spec
# Produces dist/Crier/Crier.exe (onedir). The Inno Setup script packages that folder.

import os

block_cipher = None
SPECDIR = os.path.dirname(os.path.abspath(SPEC))
ICON = os.path.join(SPECDIR, "..", "crier", "resources", "crier.ico")

a = Analysis(
    ["../crier/__main__.py"],
    pathex=["."],
    binaries=[],
    datas=[("../crier/resources/*", "crier/resources")],
    hiddenimports=[
        "PySide6.QtNetwork",
        "sounddevice",
        "kokoro_onnx",
        "onnxruntime",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PySide6.QtWebEngineCore"],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Crier",
    console=False,                 # tray app, no console window
    icon=ICON if os.path.exists(ICON) else None,
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    name="Crier",
)
