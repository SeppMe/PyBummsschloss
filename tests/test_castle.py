"""Tests for castles: geometry, support and collapse damage."""

from __future__ import annotations

from bummsschloss import config
from bummsschloss.world.castle import Castle, wrap_delta
from bummsschloss.world.terrain import Terrain


def flat(width: int = 400, height: int = 300, level: float = 200.0) -> Terrain:
    return Terrain(width, height, [level] * width)


def settle(castle: Castle, terrain: Terrain, steps: int = 4000) -> None:
    for _ in range(steps):
        if not castle.update(config.FIXED_DT, terrain):
            return


def test_castle_rests_on_the_ground():
    terrain = flat()
    castle = Castle(owner=0, centre_x=200, bottom_y=200.0)
    assert castle.update(config.FIXED_DT, terrain) is False
    assert castle.bottom_y == 200.0
    assert castle.hp == castle.max_hp


def test_undermined_castle_falls_and_takes_damage():
    terrain = flat()
    castle = Castle(owner=0, centre_x=200, bottom_y=200.0)
    # Blow a deep hole across the whole footprint.
    terrain.flatten(int(castle.left), int(castle.right), 280.0)

    settle(castle, terrain)
    castle_damage = castle.take_pending_fall_damage()

    assert castle.bottom_y == 280.0
    assert not castle.falling
    assert castle_damage > 0


def test_short_drops_are_harmless():
    terrain = flat()
    castle = Castle(owner=0, centre_x=200, bottom_y=200.0)
    terrain.flatten(int(castle.left), int(castle.right), 200.0 + config.CASTLE_SAFE_FALL - 1)

    settle(castle, terrain)
    assert castle.take_pending_fall_damage() == 0.0


def test_castle_rests_on_its_highest_support():
    """One remaining pillar is enough to hold the castle up."""
    terrain = flat()
    castle = Castle(owner=0, centre_x=200, bottom_y=200.0)
    terrain.flatten(int(castle.left), int(castle.right), 280.0)
    terrain.flatten(200, 200, 210.0)

    settle(castle, terrain)
    assert castle.bottom_y == 210.0


def test_damage_is_capped_at_zero_hp():
    castle = Castle(owner=0, centre_x=100, bottom_y=100.0)
    assert castle.damage(1000.0) == config.CASTLE_MAX_HP
    assert castle.hp == 0
    assert not castle.alive
    assert castle.damage(10.0) == 0.0


def test_contains_and_distance_respect_wrapping():
    width = 400
    castle = Castle(owner=0, centre_x=10.0, bottom_y=200.0)
    # A point just left of x=0 is right next to a castle near the left edge.
    assert castle.contains(width - 5, 160.0, width)
    assert castle.distance_to(width - 5, 160.0, width) == 0.0
    assert wrap_delta(-width + 5, width) == 5
