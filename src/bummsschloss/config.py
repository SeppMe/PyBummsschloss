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
GROUND: Final[Color] = (86, 150, 70)
GROUND_DARK: Final[Color] = (104, 72, 46)
STONE: Final[Color] = (150, 150, 160)
ACCENT: Final[Color] = (240, 196, 64)
RED: Final[Color] = (220, 72, 64)
BLUE: Final[Color] = (72, 140, 220)
GREY: Final[Color] = (120, 120, 130)

# --- Physics ----------------------------------------------------------------

#: Downward acceleration in logical pixels per second squared.
GRAVITY: Final = 420.0

# --- Match rules ------------------------------------------------------------

#: Money every player starts the match with.
STARTING_MONEY: Final = 600

#: Lump sum each player is handed at the start of their own turn.
TURN_INCOME: Final = 250

#: Wind is an acceleration in px/s^2, redrawn every turn from this range.
WIND_MAX: Final = 160.0

#: A shot is given up on after this many simulated seconds, so a freak orbit
#: around the wrapping world can never stall the game.
MAX_FLIGHT_TIME: Final = 22.0

#: How many past positions of a shot are kept for its trail.
TRAIL_LENGTH: Final = 90

#: Seconds the explosion flash stays on screen.
EXPLOSION_LIFETIME: Final = 0.45

#: Pause after a turn resolves before the next player takes over.
TURN_HANDOVER_DELAY: Final = 0.9

# --- Castles ----------------------------------------------------------------

CASTLE_WIDTH: Final = 86.0
CASTLE_HEIGHT: Final = 64.0
CASTLE_MAX_HP: Final = 100.0

#: The cannon sits this far above the castle roof.
CASTLE_MUZZLE_OFFSET: Final = 14.0

#: A drop shorter than this does no damage at all.
CASTLE_SAFE_FALL: Final = 6.0

#: Hit points lost per pixel of (unsafe) fall height.
CASTLE_FALL_DAMAGE: Final = 0.55

#: Horizontal positions of the two castles, as a fraction of the world width.
CASTLE_SPOTS: Final = (0.14, 0.86)

#: Player colours, one per seat.
PLAYER_COLORS: Final[tuple[Color, ...]] = ((220, 72, 64), (72, 140, 220))

# --- Aiming -----------------------------------------------------------------

MIN_POWER: Final = 0.05
MAX_POWER: Final = 1.0
POWER_STEP: Final = 0.02
ANGLE_STEP: Final = 0.5  # degrees per key press

