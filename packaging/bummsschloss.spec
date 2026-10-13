# PyInstaller build recipe.
#   python -m PyInstaller packaging/bummsschloss.spec
# Produces a self-contained dist/Bummsschloss2026 folder that needs no Python install.

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

project_root = Path(SPECPATH).parent
entry_script = project_root / "src" / "bummsschloss" / "__main__.py"

datas = collect_data_files("bummsschloss", subdir="assets")

a = Analysis(
    [str(entry_script)],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["bummsschloss.scenes.demo"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pydoc_data"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Bummsschloss2026",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Bummsschloss2026",
)
