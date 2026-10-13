# PyInstaller build recipe.
#   python -m PyInstaller packaging/bummsschloss.spec
# Produces a self-contained dist/Bummsschloss2026 folder that needs no Python install.

from pathlib import Path

project_root = Path(SPECPATH).parent
package_root = project_root / "src" / "bummsschloss"
entry_script = package_root / "__main__.py"

# The whole asset tree is copied into a top-level "assets" folder of the
# bundle, which is exactly where resources.assets_root() looks once the game is
# frozen. (collect_data_files would nest it under bummsschloss/ instead.)
datas = [(str(package_root / "assets"), "assets")]

# Scenes and the broker client are imported inside functions, so that --help
# does not drag in SDL and a hotseat game never touches the network. Static
# analysis does not always see through that, so they are named here.
hiddenimports = [
    "bummsschloss.scenes.lobby",
    "bummsschloss.scenes.match",
    "bummsschloss.scenes.setup",
    "bummsschloss.scenes.summary",
    "paho.mqtt.client",
    "socks",
]

a = Analysis(
    [str(entry_script)],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
