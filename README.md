# Ballerburg

A turn-based 2D artillery game (think *Gorillas* / the classic Atari *Ballerburg*),
written in Python with [pygame-ce](https://pyga.me/).

## Project layout

```
pyproject.toml          # project metadata, dependencies, tooling config
src/ballerburg/         # the game package (src-layout)
    __main__.py         # entry point:  python -m ballerburg
    app.py              # window creation + main loop
    config.py           # tunable constants
    scenes/             # one module per screen/state of the game
    assets/             # bundled data files (images, levels, fonts)
tests/                  # pytest suite (runs headless)
```

## Development setup

```powershell
# Windows
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m ballerburg
```

```bash
# Linux / macOS
python -m pip install -e ".[dev]"
python -m ballerburg
```

### Useful commands

| Task | Command |
| --- | --- |
| Run the game | `python -m ballerburg` |
| Run the ball demo | `python -m ballerburg --scene demo` |
| Run tests | `python -m pytest` |
| Lint | `python -m ruff check .` |

## Packaging

### Wheel / sdist (for other Python users)

```powershell
python -m pip install build
python -m build
```

Produces `dist/ballerburg-<version>-py3-none-any.whl`, installable anywhere with
`pip install ballerburg-<version>-py3-none-any.whl`. It registers the `ballerburg`
console command.

### Standalone executable (for machines without Python)

```powershell
python -m pip install -e ".[build]"
python -m PyInstaller packaging/ballerburg.spec
```

Produces `dist/Ballerburg/Ballerburg.exe` (one folder, starts fastest).
The same spec works on Linux/macOS.
