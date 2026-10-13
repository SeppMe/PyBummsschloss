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
    match.py              # the rules engine (no pygame)
    matchsetup.py         # the pre-match choices (no pygame)
    weapons.py            # the arsenal
    stats.py              # per-player statistics and the awards
    resources.py          # asset lookup / loading
    world/                # terrain, castles, projectiles (no pygame)
    scenes/               # one module per screen/state of the game
    assets/               # bundled data files (images, levels, fonts)
tests/                    # pytest suite (runs headless)
packaging/                # PyInstaller recipe
```

The rules engine (`match.py`, `matchsetup.py`, `world/`, `weapons.py`,
`stats.py`) never imports pygame. Everything the players see lives in
`scenes/`. That split keeps the simulation testable headless today, and makes
it reusable as the authoritative side of a network game later.

## How the game works

### Setting up a match

The game opens on a setup menu. Arrow keys (or the mouse) pick a row and change
its value, Enter starts the match:

| Setting | Choices |
| --- | --- |
| Players | 2 to 4, each with their own castle |
| Seat | Type to rename, arrows pick one of six colours |
| Starting money | What everybody begins with |
| Income per turn | The base lump sum |
| Economy | How that lump sum is worked out (see below) |

Two seats never share a colour; stepping through the palette skips whatever is
already taken. The three economies are:

- **flat** - everybody gets the same amount every turn.
- **rising** - the income grows each round, so the expensive weapons eventually
  become affordable and matches do not drag on.
- **catch-up** - the more battered your castle, the more you are paid, which
  keeps a losing player in the game.

### Playing

Two to four castles sit in a randomly generated, horizontally **wrapping**
landscape of one to three big flowing hills. Each castle gets its own slot
around the world, but where exactly it stands inside that slot - and which
seat gets which slot - is drawn afresh every match, so nobody owns the left
side. Players take turns (hotseat) lobbing shells at each other; a destroyed
castle is skipped, and the last one standing wins.

**Terrain** is a heightmap: one surface height per pixel column. When a shell
digs material out of the middle of a column, everything above it drops by the
same amount, so craters collapse rather than leaving floating ceilings.

**Castles** are statically placed and do not move sideways, but they rest on
the ground under their footprint. Blow that ground away and the castle topples,
taking damage proportional to the drop. A single surviving pillar is enough to
hold it up.

**Wind** is rerolled every turn and acts as a sideways acceleration. How much a
shot cares about it is the weapon's `wdabhkt`
(*Windabhängigkeitskoeffizient*): an iron ball barely notices the breeze,
a balloon bomb is at its mercy, a laser ignores it entirely. Each weapon also
scales gravity separately, so mortars plummet while balloons never come down.

### The arsenal

The bottom of the screen names every weapon with its price, explains what the
selected one does, and lists its numbers. **W** opens the whole table at once.

| Weapon | Cost | What makes it special |
| --- | --- | --- |
| Dud | 0 | Free. Skip a turn to save up - or finish someone off with it |
| Cannonball | 50 | Cheap, heavy, barely troubled by the wind |
| Mortar shell | 180 | Falls steeply, for targets behind a hill |
| Balloon bomb | 220 | No gravity at all; rides the wind until it hits something |
| Mole | 260 | Digs into the hill and noses back out; ignores your own castle |
| Cluster barrel | 340 | Bursts at the top of its arc into five bomblets |
| Earthquake | 420 | Hits *every* castle for the same amount - including your own |
| Laser | 480 | Dead straight: no gravity, no wind |
| Fat Bertha | 600 | A huge crater, and damage to match |

Because the dud is free, a player can always take a turn, even when broke.

**The playfield wraps.** A shot leaving the right edge comes back in on the
left. Leaving the top or bottom of the screen is not an escape either - the
trajectory keeps being simulated out of sight, with an on-screen marker showing
where the shot currently is. A flight-time limit stops a freak orbit from
stalling the game.

**Economy**: each player receives a lump sum at the start of their own turn and
spends it on shells. There is no base building; how the sum is worked out is
chosen in the setup menu.

**After the match** a summary screen compares every player and hands out awards
for greatest total damage, best single shot, damage per shot, most castles
destroyed, best hit rate, and a few less flattering distinctions.

### Controls

| Input | Action |
| --- | --- |
| Mouse | Aim |
| Click / Space | Fire |
| Left / Right | Fine-tune the angle |
| Up / Down, wheel | Power |
| 1-9, Tab | Choose a weapon |
| W | Show the arsenal |
| M | Back to the setup menu |
| H | Help |
| F11 | Fullscreen |
| Esc / Q | Quit |

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
| Skip the menu | `python -m bummsschloss --scene match` |
| Preselect four players | `python -m bummsschloss --players 4` |
| Run a reproducible match | `python -m bummsschloss --seed 1234` |
| Run the old engine demo | `python -m bummsschloss --scene demo` |
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
