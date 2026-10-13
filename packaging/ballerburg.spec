# PyInstaller build recipe.
#   python -m PyInstaller packaging/ballerburg.spec
# Produces a self-contained dist/Ballerburg folder that needs no Python install.

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

project_root = Path(SPECPATH).parent
entry_script = project_root / "src" / "ballerburg" / "__main__.py"

datas = collect_data_files("ballerburg", subdir="assets")

a = Analysis(
    [str(entry_script)],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["ballerburg.scenes.demo"],
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
    name="Ballerburg",
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
    name="Ballerburg",
)
