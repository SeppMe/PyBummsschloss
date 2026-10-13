# Das quietschfidele Bummsschloss

*Bummsschloss 2026* — ein rundenbasiertes 2D-Artilleriespiel (in der Tradition von
*Gorillas* und der Atari-Klassiker *Ballerburg*), geschrieben in Python mit
[pygame-ce](https://pyga.me/).

A turn-based 2D artillery game. The user interface is German by default; all code,
comments and source strings are English.

## Project layout

```
pyproject.toml            # project metadata, dependencies, tooling config
src/bummsschloss/         # the game package (src-layout)
    __main__.py           # entry point:  python -m bummsschloss
    app.py                # window creation + main loop
    config.py             # tunable constants
    i18n.py               # translation catalogues and the _() helper
    resources.py          # asset lookup / loading
    scenes/               # one module per screen/state of the game
    assets/               # bundled data files (images, levels, fonts)
tests/                    # pytest suite (runs headless)
packaging/                # PyInstaller recipe
```

## Development setup

```powershell
# Windows
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m bummsschloss
```

```bash
# Linux / macOS
python -m pip install -e ".[dev]"
python -m bummsschloss
```

### Useful commands

| Task | Command |
| --- | --- |
| Run the game | `python -m bummsschloss` |
| Run the ball demo | `python -m bummsschloss --scene demo` |
| Run in English | `python -m bummsschloss --lang en` |
| Run tests | `python -m pytest` |
| Lint | `python -m ruff check .` |

## Translations

All user-visible text goes through `_()` from `bummsschloss.i18n`, which looks the
English source string up in a per-language dictionary. To add a language, add its
code to `AVAILABLE_LANGUAGES` and a catalogue to `CATALOGUES` in that module.
The language is chosen from `--lang`, then the `BUMMSSCHLOSS_LANG` environment
variable, then the system locale, falling back to German.

## Packaging

### Wheel / sdist (for other Python users)

```powershell
python -m pip install build
python -m build
```

Produces `dist/bummsschloss_2026-<version>-py3-none-any.whl`, installable anywhere
with `pip install`. It registers the `bummsschloss` console command.

### Standalone executable (for machines without Python)

```powershell
python -m pip install -e ".[build]"
python -m PyInstaller packaging/bummsschloss.spec
```

Produces `dist/Bummsschloss2026/Bummsschloss2026.exe` (one folder, starts fastest).
The same spec works on Linux/macOS.
