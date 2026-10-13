"""Flying things.

A projectile is a point mass. What makes each weapon feel different is the
pair of coefficients it carries: how strongly gravity pulls on it
(``gravity_scale``) and how strongly the wind pushes it (``wdabhkt``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bummsschloss import config
from bummsschloss.weapons import Weapon


@dataclass
class Projectile:
    """A shot in flight."""

    x: float
    y: float
    vx: float
    vy: float
    weapon: Weapon
    owner: int

    #: Seconds this projectile has been in the air.
    age: float = 0.0
    #: Recent positions, for drawing a trail. Stored unwrapped-per-point.
    trail: list[tuple[float, float]] = field(default_factory=list)
    #: Cleared once a cluster weapon has split, so it only happens once.
    can_split: bool = True

    def step(self, dt: float, wind: float) -> None:
        """Advance one tick. ``wind`` is an acceleration in px/s^2."""
        self.vx += wind * self.weapon.wdabhkt * dt
        self.vy += config.GRAVITY * self.weapon.gravity_scale * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.age += dt

        self.trail.append((self.x, self.y))
        if len(self.trail) > config.TRAIL_LENGTH:
            del self.trail[0]

    @property
    def expired(self) -> bool:
        """True when the shot has been flying for implausibly long.

        Without this a very light, very wind-blown shot could in principle
        circle the wrapping world forever and stall the turn.
        """
        return self.age >= config.MAX_FLIGHT_TIME

    @property
    def past_apex(self) -> bool:
        """True once the projectile has started falling again."""
        return self.vy > 0.0
