"""Flying things.

A projectile is a point mass. What makes each weapon feel different is the
pair of coefficients it carries: how strongly gravity pulls on it
(``gravity_scale``) and how strongly the wind pushes it (``wdabhkt``).

One weapon leaves that model behind: a burrowing round keeps going once it
enters the ground, nosing steadily upwards as it digs until it either breaks
back out into the open or runs out of budget.
"""

from __future__ import annotations

import math
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
    #: True while the round is tunnelling through solid ground.
    burrowing: bool = False
    #: Pixels of digging left before a burrowing round goes off.
    burrow_left: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        self.burrow_left = self.weapon.burrow_depth

    def step(self, dt: float, wind: float) -> None:
        """Advance one tick. ``wind`` is an acceleration in px/s^2."""
        if self.burrowing:
            self._dig(dt)
            return

        self.vx += wind * self.weapon.wdabhkt * dt
        self.vy += config.GRAVITY * self.weapon.gravity_scale * dt
        self._advance(dt)

    def _dig(self, dt: float) -> None:
        """Bore through the earth, nosing upwards all the while.

        Wind and gravity have no say underground. Instead the round is pushed
        up by ``burrow_lift``, which bends the tunnel back towards daylight
        like a cannon fired in reverse. The pace is capped at ``burrow_speed``
        so that digging stays slower than flying, but it is free to drop below
        that while the round turns around.
        """
        self.vy -= self.weapon.burrow_lift * dt
        speed = math.hypot(self.vx, self.vy)
        if speed > self.weapon.burrow_speed > 0.0:
            scale = self.weapon.burrow_speed / speed
            self.vx *= scale
            self.vy *= scale
            speed = self.weapon.burrow_speed
        self.burrow_left -= speed * dt
        self._advance(dt)

    def _advance(self, dt: float) -> None:
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.age += dt

        self.trail.append((self.x, self.y))
        if len(self.trail) > config.TRAIL_LENGTH:
            del self.trail[0]

    def start_burrowing(self) -> None:
        """Called the moment the round first bites into the ground."""
        self.burrowing = True

    def stop_burrowing(self) -> None:
        """Called when the round breaks back out into the open air.

        It keeps whatever tunnelling budget is left, so a round that pops out
        of one hillside can still dig into the next one.
        """
        self.burrowing = False

    @property
    def can_burrow(self) -> bool:
        """True while a digging round still has budget left to tunnel with."""
        return self.weapon.burrows and self.burrow_left > 0.0

    @property
    def burrow_exhausted(self) -> bool:
        """True once a digging round has used up its tunnel and must go off."""
        return self.burrowing and self.burrow_left <= 0.0

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
