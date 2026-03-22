# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build graph for **ACID2Reaper**.

Build from the project root after installing the package:
    pip install .
    pip install ".[pyinstaller]"
    python scripts/verify_changelog.py
    pyinstaller packaging/pyinstaller.spec

On macOS this produces ``ACID2Reaper.app``; on Windows/Linux, ``dist/ACID2Reaper/``.
"""
import sys
from pathlib import Path


def _project_root() -> Path:
    """
    Find the repository root by walking upward from this spec file until we see
    pyproject.toml. This avoids brittle ``parent.parent`` math when paths contain
    spaces or PyInstaller is launched from an unexpected cwd.
    """
    here = Path(SPECPATH).resolve().parent
    for _ in range(8):
        if (here / "pyproject.toml").is_file():
            return here
        parent = here.parent
        if parent == here:
            break
        here = parent
    raise RuntimeError(f"Cannot locate project root (pyproject.toml) near {SPECPATH!r}")


project_root = _project_root()
src = project_root / "src"
assets = project_root / "assets"
packaging_dir = project_root / "packaging"

_ver_ns: dict = {}
exec((src / "acid2reaper" / "_version.py").read_text(encoding="utf-8"), _ver_ns)
APP_VERSION = _ver_ns["__version__"]

datas = [
    (str(src / "acid2reaper" / "data" / "acd_signatures.json"), "acid2reaper/data"),
]

hiddenimports = [
    "rpp",
    "rpp.element",
    "rpp.encoder",
    "rpp.decoder",
    "rpp.scanner",
    "tkinter",
    "tkinter.ttk",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "tkinter.font",
]

icon_path = assets / "acid2reaper_logo.png"

a = Analysis(
    [str(packaging_dir / "launcher_gui.py")],
    pathex=[str(src)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

gui_exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ACID2Reaper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    gui_exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="ACID2Reaper",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="ACID2Reaper.app",
        icon=str(icon_path) if icon_path.is_file() else None,
        bundle_identifier="com.acid2reaper.gui",
        info_plist={
            "CFBundleName": "ACID2Reaper",
            "CFBundleDisplayName": "ACID2Reaper",
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "NSHighResolutionCapable": True,
        },
    )
