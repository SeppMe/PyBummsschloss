"""Tunable constants for the whole game.

Everything a designer might want to tweak lives here so that gameplay code
stays free of magic numbers.
"""

from __future__ import annotations

from random import Random
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

#: How far above the screen a gravity-free shot must be before it is written
#: off. Such a shot cannot fall back, so waiting for the flight timer would
#: only bore the players.
LOST_IN_SKY_MARGIN: Final = 400.0

#: How many past positions of a shot are kept for its trail.
TRAIL_LENGTH: Final = 90

#: Seconds the explosion flash stays on screen.
EXPLOSION_LIFETIME: Final = 0.45

#: Pause after a turn resolves before the next player takes over.
TURN_HANDOVER_DELAY: Final = 0.9

# --- Castles ----------------------------------------------------------------

CASTLE_WIDTH: Final = 52.0
CASTLE_HEIGHT: Final = 38.0
CASTLE_MAX_HP: Final = 100.0

#: The cannon sits this far above the castle roof.
CASTLE_MUZZLE_OFFSET: Final = 9.0

#: A drop shorter than this does no damage at all.
CASTLE_SAFE_FALL: Final = 6.0

#: Hit points lost per pixel of (unsafe) fall height.
CASTLE_FALL_DAMAGE: Final = 0.55

#: How far a castle may wander from the middle of its slot, as a fraction of
#: the slot width. Keeping it below 0.5 guarantees the castles never swap
#: places or crowd each other, however the dice fall.
CASTLE_SPOT_JITTER: Final = 0.34

#: Columns of eased ground on either side of a castle's plateau, so that a
#: castle on a slope sits on a shoulder instead of a sheer pillar.
CASTLE_APRON: Final = 55


#: Castle positions are spread evenly around the wrapping world, so that every
#: seat has roughly the same distance to both of its neighbours.
def castle_spots(count: int, rng: Random | None = None) -> tuple[float, ...]:
    """Return the castle positions for ``count`` players, as fractions of the width.

    Without an ``rng`` the slots are dead even. With one, the whole ring is
    rotated by a random amount and every castle is nudged within its own slot,
    so no two landscapes put the castles in quite the same place.
    """
    slot = 1.0 / count
    if rng is None:
        return tuple((index + 0.5) * slot for index in range(count))

    offset = rng.random()
    reach = slot * CASTLE_SPOT_JITTER
    return tuple(
        ((index + 0.5) * slot + offset + rng.uniform(-reach, reach)) % 1.0
        for index in range(count)
    )


#: How many seats a match can have.
MIN_PLAYERS: Final = 2
MAX_PLAYERS: Final = 4

#: Selectable player colours: source name for translation plus the RGB value.
PLAYER_PALETTE: Final[tuple[tuple[str, Color], ...]] = (
    ("red", (220, 72, 64)),
    ("blue", (72, 140, 220)),
    ("green", (96, 200, 104)),
    ("yellow", (236, 204, 80)),
    ("purple", (176, 112, 220)),
    ("orange", (240, 140, 60)),
)


def player_color(color_index: int) -> Color:
    """Return the RGB value of a palette entry, wrapping on overflow."""
    return PLAYER_PALETTE[color_index % len(PLAYER_PALETTE)][1]


def player_color_name(color_index: int) -> str:
    """Return the untranslated source name of a palette entry."""
    return PLAYER_PALETTE[color_index % len(PLAYER_PALETTE)][0]


# --- Economy options --------------------------------------------------------
# Values offered in the pre-match menu.

STARTING_MONEY_CHOICES: Final[tuple[int, ...]] = (0, 300, 600, 1200, 2500)
TURN_INCOME_CHOICES: Final[tuple[int, ...]] = (100, 250, 400, 700)

#: "Rising" economy: each full round adds this share of the base income.
INCOME_RISE_PER_ROUND: Final = 0.25

#: "Catch-up" economy: a castle at death's door earns up to this much extra.
INCOME_CATCHUP_BONUS: Final = 1.0

# --- Aiming -----------------------------------------------------------------

MIN_POWER: Final = 0.05
MAX_POWER: Final = 1.0
POWER_STEP: Final = 0.02
ANGLE_STEP: Final = 0.5  # degrees per key press

