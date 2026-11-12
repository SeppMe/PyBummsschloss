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
    diagnostics.py        # the machine check behind --diagnose
    world/                # terrain, castles, projectiles (no pygame)
    net/                  # lockstep network play over a message broker
    scenes/               # one module per screen/state of the game
    assets/               # bundled data files
        images/           # sprites and backgrounds
        sounds/           # sound effects
        fonts/            # bundled typefaces
tests/                    # pytest suite (runs headless)
tools/                    # small diagnostics (e.g. finding a working broker)
packaging/                # PyInstaller recipe
```

The rules engine (`match.py`, `matchsetup.py`, `world/`, `weapons.py`,
`stats.py`) never imports pygame. Everything the players see lives in
`scenes/`. That split keeps the simulation testable headless, and it is what
makes network play cheap: `net/` drives the very same engine from messages
instead of from a keyboard.

## How the game works

### Setting up a match

The game opens on a setup menu. Arrow keys (or the mouse) pick a row and change
its value, Enter starts the match:

| Setting | Choices |
| --- | --- |
| Game type | Hotseat at one keyboard, or a networked game (see below) |
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

## Playing over the internet

Set **Game type** to *network*. One player is the **host**: they get a
five-character room code, read it out to the others, and the others set their
role to *join* and type that code in. Everybody lands in a waiting room; the
host presses Enter and the match begins.

There is nothing to install and nothing to forward. All the clients connect
*outwards* to a free public MQTT broker and subscribe to a topic named after
the room code, so the broker is only ever a postbox - no accounts, no server of
our own, and no inbound ports on anybody's router.

What travels is only what a player *decided*: their weapon, angle and power.
Every client then runs exactly the same simulation. The world itself is never
recomputed independently - the host generates it once and sends it as a
snapshot - and after every turn the host publishes a short hash of the world.
A client whose hash differs asks for a fresh snapshot and carries straight on,
so a floating-point difference between two machines can cost a bit of
animation but never the match.

### If it will not connect

Networks differ, especially at the office. The default broker speaks MQTT
inside a TLS WebSocket, which looks exactly like HTTPS and therefore gets
through most firewalls; if `HTTPS_PROXY` is set in the environment, the game
tunnels through that proxy like a browser would. To find out what works on your
network:

```
python tools/netcheck.py
```

It tries each known broker, plays an actual turn across it, and prints the ones
that worked. Pass a working address to the game - everybody in the match must
use the same one:

```
bummsschloss --broker wss://test.mosquitto.org:8081/mqtt
```

The address can also be set once via the `BUMMSSCHLOSS_BROKER` environment
variable. Addresses look like `wss://host:port/path` or `tcp://host:port`.

Two caveats worth knowing: a public broker is public, so anybody who guesses
your room code can watch (and join) the game, and a player who disappears
mid-match simply stalls their own turn - there is no AI to take over.

## If it will not start on somebody else's machine

"It does not work" is all the report you usually get, because the failures
that matter here kill the process outright and so never print a traceback.
Ask for this instead:

```
bummsschloss --diagnose                     # installed from the wheel
Bummsschloss2026-Diagnose.exe               # the standalone build
```

It prints the machine - CPU model, which instruction-set extensions that CPU
actually has, Python and pygame-ce versions - and then walks through the
things that can go wrong, each **in its own child process**: the rules engine
on its own (no pygame at all), importing pygame, starting SDL, opening a
window, the blitters, the fillers, the transforms, image decoding, text
rendering, audio, and finally one real frame of the real menu. A probe that
takes its process down with it therefore cannot take the report down with it;
the parent decodes the exit status - `SIGILL` on Linux, `0xC000001D` on
Windows, both meaning "this CPU does not know that instruction" - and names
the step. The first failure in the list is the one to chase. If `import
pygame` is what dies, the report adds the trail of modules that did load, so
even a crash with no traceback points at an extension module.

The parent process never imports pygame itself, for the obvious reason: on
the machine being diagnosed, that import may be precisely what crashes.

A copy of the report is always written to `bummsschloss-diagnose.txt` in the
user's home directory, which matters for the standalone build, where the game
itself has no console to print to.

### A note on old CPUs

The wheel is `py3-none-any`: it contains no machine code at all, so it cannot
itself use an instruction a processor does not have. Every byte of machine
code comes from pygame-ce, the SDL libraries and CPython, and all three pick
their AVX2 paths at *runtime* after asking the CPU (`SDL_HasAVX2()` in SDL and
in pygame-ce's blitters, a CPUID probe in CPython's hashing and zlib code).
Those AVX2 instructions are therefore present in the binaries but unreachable
on a processor that cannot run them, which makes a missing AVX2 an unlikely
explanation for a crash.

**32-bit x86 is the exception worth knowing about.** On x86-64, SSE2 is part
of the ABI, so every 64-bit chip has it and compilers may emit it freely. On
32-bit x86 it is optional: anything older than a Pentium 4 or Pentium M does
not have SSE2 at all. pygame-ce does publish `manylinux2014_i686` wheels, so
`pip` will happily install a prebuilt binary on a 32-bit Debian - and that
binary was built and tested on hardware far newer than the machine it may end
up on. This is why the machine check reports `SSE`, `SSE2`, `MMX` and `CMOV`
alongside the newer extensions, and says so plainly when it finds a 32-bit
CPU without SSE2.

None of this is fixable by packaging the game differently, which is exactly
why the check reports the CPU's own feature flags *and* isolates the failing
component instead of guessing.

**This has been confirmed by disassembly.** In the published
`pygame_ce-2.5.8-cp313-...-manylinux2014_i686` wheel, x87 is the default
floating-point path, so the library was *not* built wholesale for SSE2 - but
the compiler still emitted SSE2 opportunistically in ordinary, non-SIMD code.
For example `pg_TwoDoublesFromObj` in `pygame/base.so`, the helper that turns
Python numbers into C doubles for every `pygame.draw` call, `Rect` and
`Vector2`, copies a `double` with `movsd xmm0, [ebp+8]`. That module contains
no `cpuid` instruction anywhere, so the choice is not guarded: on a CPU
without SSE2 it is an illegal instruction the moment the first frame is drawn.
SDL2 itself is well behaved by comparison - it does use CPUID and dispatches
properly - so the problem is pygame-ce's own extension modules, not SDL.

The remedy, if a machine turns out to lack SSE2, is to avoid the prebuilt
wheel and let the distribution's own compiler (whose i686 baseline does not
assume SSE2) generate the code:

```bash
sudo apt install build-essential python3-dev pkg-config \
  libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
  libfreetype6-dev libportmidi-dev
CFLAGS="-march=pentium3 -mtune=generic -mfpmath=387" \
  pip install --no-binary pygame-ce --force-reinstall pygame-ce
```

`-march=pentium3` allows SSE but not SSE2, and `-mfpmath=387` keeps ordinary
floating-point arithmetic on the x87 stack. (Use `-march=pentium2` for a CPU
with no SSE at all.) The flags are belt and braces rather than strictly
necessary - the distribution compiler's own i686 default already avoids SSE2 -
but they make the requirement explicit and fail loudly if it is ever violated.

Setting them is safe: pygame-ce guards its hand-written SSE2 blitters with
`#if defined(__SSE2__)` and passes no `-msse2` of its own on x86, so without
that flag those files simply compile to nothing and the portable C versions
are used instead. The result is a slower but correct build.

On Linux a source build links the system SDL instead of vendoring its own, so
this replaces both halves of the problem at once. Re-run `--diagnose`
afterwards: the `math` and `draw` probes are the ones that fail first on a
CPU without SSE2.

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
| Run in English | `python -m bummsschloss --lang en` |
| Run tests | `python -m pytest` |
| Lint | `python -m ruff check .` |
| Check a machine that will not run it | `bummsschloss --diagnose` |

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

Produces `dist/Bummsschloss2026/Bummsschloss2026.exe` (one folder, starts fastest),
and next to it `Bummsschloss2026-Diagnose.exe`, the same program attached to a
console and running the machine check described above.
The same spec works on Linux/macOS.
