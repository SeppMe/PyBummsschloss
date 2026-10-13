"""The destructible landscape.

The terrain is stored as a *heightmap*: one surface height per pixel column,
with everything below that height being solid rock. That representation gives
us the collapse behaviour for free - when an explosion removes material from
the middle of a column, everything above it simply drops down by the same
amount, so craters can never leave floating ceilings or Swiss-cheese caves.

The world wraps horizontally: column ``-1`` is the same as column ``width - 1``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from random import Random

#: How many major hills a landscape may have. One makes for a single great
#: mountain with the players on its flanks, three for a proper range.
MIN_PEAKS = 1
MAX_PEAKS = 3


class Terrain:
    """A horizontally wrapping heightmap of solid ground."""

    def __init__(self, width: int, height: int, heights: Sequence[float]) -> None:
        if len(heights) != width:
            raise ValueError("heights must have one entry per column")
        self.width = width
        self.height = height
        self._heights = [float(h) for h in heights]
        #: Bumped on every change so renderers know to rebuild their cache.
        self.version = 0

    # -- construction -------------------------------------------------------

    @classmethod
    def generate(
        cls,
        width: int,
        height: int,
        rng: Random,
        *,
        min_height: float = 0.32,
        max_height: float = 0.92,
    ) -> Terrain:
        """Create a random landscape of a few big hills that tiles seamlessly.

        The shape is built from a handful of sine waves. One of them carries
        almost all of the relief: it decides whether the map has one great
        mountain or three, and everything else is a small modulation on top,
        so the result flows rather than ripples.

        Only whole-number frequencies are used, so the left and right edges
        always match up and shots can fly across the seam unnoticed.
        """
        peaks = rng.randint(MIN_PEAKS, MAX_PEAKS)
        waves = [
            # The main ridge, and the long swell that makes one side of the
            # map grander than the other.
            (peaks, 1.0),
            (1, 0.45 if peaks > 1 else 0.25),
            # Shoulders and foothills, just enough to break the symmetry.
            (peaks * 2, 0.16),
            (peaks * 3 + 1, 0.07),
        ]

        raw = []
        phases = [rng.uniform(0.0, math.tau) for _ in waves]
        for x in range(width):
            t = x / width
            value = sum(
                amplitude * math.sin(math.tau * frequency * t + phase)
                for (frequency, amplitude), phase in zip(waves, phases, strict=True)
            )
            raw.append(value)

        lo, hi = min(raw), max(raw)
        span = (hi - lo) or 1.0
        top = height * min_height
        bottom = height * max_height
        heights = [top + (bottom - top) * (1.0 - (value - lo) / span) for value in raw]
        return cls(width, height, heights)

    # -- queries ------------------------------------------------------------

    def wrap_x(self, x: float) -> float:
        """Wrap a horizontal coordinate into the playfield."""
        return x % self.width

    def column(self, x: float) -> int:
        """The column index for a (possibly out-of-range) x coordinate."""
        return int(self.wrap_x(x)) % self.width

    def height_at(self, x: float) -> float:
        """Surface height (smaller y is higher up) at the given x."""
        return self._heights[self.column(x)]

    def heights(self) -> list[float]:
        """A copy of the whole heightmap."""
        return list(self._heights)

    def is_solid(self, x: float, y: float) -> bool:
        """Is the given point inside the ground?"""
        return y >= self.height_at(x)

    def surface_between(self, x0: int, x1: int) -> float:
        """Highest ground surface (smallest y) across a range of columns."""
        return min(self._heights[self.column(x)] for x in range(x0, x1 + 1))

    def average_surface(self, x0: int, x1: int) -> float:
        """Mean ground surface across a range of columns.

        Seating a castle at the average cuts the high side down and fills the
        low side in, instead of raising the whole span onto a pillar.
        """
        columns = range(x0, x1 + 1)
        return sum(self._heights[self.column(x)] for x in columns) / len(columns)

    # -- modification -------------------------------------------------------

    def flatten(self, x0: int, x1: int, level: float | None = None, blend: int = 0) -> float:
        """Level the ground between two columns, e.g. to seat a castle.

        ``blend`` adds an apron of that many columns on either side, easing
        from the new level back into the untouched landscape so that a castle
        on a hillside gets a shoulder rather than a cliff.
        """
        if level is None:
            level = self.surface_between(x0, x1)
        for x in range(x0, x1 + 1):
            self._heights[self.column(x)] = level
        for offset in range(1, blend + 1):
            t = offset / (blend + 1)
            weight = t * t * (3.0 - 2.0 * t)
            for x in (x0 - offset, x1 + offset):
                index = self.column(x)
                self._heights[index] = level * (1.0 - weight) + self._heights[index] * weight
        self.version += 1
        return level

    def explode(self, cx: float, cy: float, radius: float) -> None:
        """Blast a circular hole and let the material above collapse into it.

        For every affected column we work out how much *solid* material the
        circle covers and lower the surface by exactly that much, which is the
        same as the ground above the hole falling down to fill it.
        """
        if radius <= 0:
            return
        reach = int(math.ceil(radius))
        for offset in range(-reach, reach + 1):
            half_chord = radius * radius - offset * offset
            if half_chord <= 0:
                continue
            half_chord = math.sqrt(half_chord)
            circle_top = cy - half_chord
            circle_bottom = cy + half_chord

            index = self.column(cx + offset)
            surface = self._heights[index]
            # Only the part of the circle that is actually underground counts.
            removed = circle_bottom - max(circle_top, surface)
            if removed <= 0:
                continue
            self._heights[index] = min(self.height, surface + removed)
        self.version += 1

    # -- helpers ------------------------------------------------------------

    def polygon_points(self) -> Iterable[tuple[int, int]]:
        """Outline of the solid ground, ready for ``pygame.draw.polygon``."""
        yield (0, self.height)
        for x, h in enumerate(self._heights):
            yield (x, int(h))
        yield (self.width - 1, self.height)
