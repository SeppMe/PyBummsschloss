"""Castles: the static bases the players shoot at.

A castle occupies a fixed range of terrain columns. It does not move
horizontally, but it is *not* nailed to the sky either: once the ground
underneath is blasted away it falls, and the drop hurts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bummsschloss import config
from bummsschloss.world.terrain import Terrain


@dataclass
class Castle:
    """One player's base."""

    owner: int
    centre_x: float
    bottom_y: float
    width: float = config.CASTLE_WIDTH
    height: float = config.CASTLE_HEIGHT
    hp: float = config.CASTLE_MAX_HP
    max_hp: float = config.CASTLE_MAX_HP

    #: Vertical speed while falling; zero whenever the castle rests on ground.
    fall_speed: float = 0.0
    falling: bool = False
    #: Damage earned by the last landing, waiting for the match to attribute
    #: it to whoever dug the ground away. Read and cleared by the rules engine.
    pending_fall_damage: float = 0.0
    #: How far the castle has dropped in the current fall, used for damage.
    _fall_distance: float = field(default=0.0, repr=False)

    # -- geometry -----------------------------------------------------------

    @property
    def left(self) -> float:
        return self.centre_x - self.width / 2

    @property
    def right(self) -> float:
        return self.centre_x + self.width / 2

    @property
    def top_y(self) -> float:
        return self.bottom_y - self.height

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def muzzle(self) -> tuple[float, float]:
        """Where this castle's shots are spawned - the top of the tower."""
        return (self.centre_x, self.top_y - config.CASTLE_MUZZLE_OFFSET)

    def contains(self, x: float, y: float, world_width: int) -> bool:
        """Is the point inside the castle, taking the wrapping world into account?"""
        dx = wrap_delta(x - self.centre_x, world_width)
        return abs(dx) <= self.width / 2 and self.top_y <= y <= self.bottom_y

    def distance_to(self, x: float, y: float, world_width: int) -> float:
        """Shortest distance from a point to the castle's bounding box."""
        dx = abs(wrap_delta(x - self.centre_x, world_width)) - self.width / 2
        dy = max(self.top_y - y, y - self.bottom_y)
        dx = max(dx, 0.0)
        dy = max(dy, 0.0)
        return (dx * dx + dy * dy) ** 0.5

    # -- support and falling ------------------------------------------------

    def support_level(self, terrain: Terrain) -> float:
        """The y the castle would rest at, given the ground under its footprint."""
        return terrain.surface_between(int(self.left), int(self.right))

    def update(self, dt: float, terrain: Terrain) -> bool:
        """Advance the castle's fall. Returns True while it is still moving."""
        support = self.support_level(terrain)
        if self.bottom_y >= support - 0.5 and not self.falling:
            self.bottom_y = support
            return False

        if not self.falling:
            self.falling = True
            self.fall_speed = 0.0
            self._fall_distance = 0.0

        self.fall_speed += config.GRAVITY * dt
        step = self.fall_speed * dt
        if self.bottom_y + step >= support:
            self._fall_distance += support - self.bottom_y
            self.bottom_y = support
            self.land()
            return False

        self.bottom_y += step
        self._fall_distance += step
        return True

    def land(self) -> float:
        """Stop falling and work out the damage the drop caused.

        The damage is *not* applied here: it is parked in
        :attr:`pending_fall_damage` so the rules engine can credit it to the
        player whose shot dug the ground away.
        """
        distance = self._fall_distance
        self.falling = False
        self.fall_speed = 0.0
        self._fall_distance = 0.0
        if distance > config.CASTLE_SAFE_FALL:
            self.pending_fall_damage += (
                distance - config.CASTLE_SAFE_FALL
            ) * config.CASTLE_FALL_DAMAGE
        return self.pending_fall_damage

    def take_pending_fall_damage(self) -> float:
        """Hand the parked fall damage over to the caller and reset it."""
        amount = self.pending_fall_damage
        self.pending_fall_damage = 0.0
        return amount

    # -- damage -------------------------------------------------------------

    def damage(self, amount: float) -> float:
        """Apply damage and return how much was actually dealt."""
        amount = max(0.0, min(amount, self.hp))
        self.hp -= amount
        return amount


def wrap_delta(delta: float, world_width: int) -> float:
    """Shortest signed horizontal distance in a world that wraps around."""
    return (delta + world_width / 2) % world_width - world_width / 2
