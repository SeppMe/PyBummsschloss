"""Tunable constants for the whole game.

Everything a designer might want to tweak lives here so that gameplay code
stays free of magic numbers.
"""

from __future__ import annotations

from typing import Final

# --- Window -----------------------------------------------------------------

GAME_TITLE: Final = "Das quietschfidele Bummsschloss"

#: Short form used where space is tight (window lists, file names, builds).
GAME_SHORT_TITLE: Final = "Bummsschloss 2026"

#: The fixed resolution the game is drawn at. The window may be any size; the
#: rendered surface is scaled to fit while preserving this aspect ratio.
LOGICAL_SIZE: Final = (960, 540)

#: Initial on-screen window size.
WINDOW_SIZE: Final = (1280, 720)

#: Frames per second the main loop aims for.
FPS: Final = 60

#: Fixed simulation step in seconds. Physics is advanced in increments of this
#: value so the simulation is deterministic and frame-rate independent, which
#: also keeps future network play in sync.
FIXED_DT: Final = 1.0 / 120.0

#: Safety net: never simulate more than this many seconds in one frame.
MAX_FRAME_TIME: Final = 0.25

# --- Palette ----------------------------------------------------------------
# A deliberately small, flat palette in the spirit of the old EGA/VGA demos.

Color = tuple[int, int, int]

BLACK: Final[Color] = (0, 0, 0)
WHITE: Final[Color] = (255, 255, 255)
SKY: Final[Color] = (24, 32, 64)
SKY_LOW: Final[Color] = (84, 60, 96)
GROUND: Final[Color] = (46, 92, 54)
GROUND_DARK: Final[Color] = (28, 58, 36)
STONE: Final[Color] = (150, 150, 160)
ACCENT: Final[Color] = (240, 196, 64)
RED: Final[Color] = (220, 72, 64)
BLUE: Final[Color] = (72, 140, 220)
GREY: Final[Color] = (120, 120, 130)

# --- Physics ----------------------------------------------------------------

#: Downward acceleration in logical pixels per second squared.
GRAVITY: Final = 420.0
