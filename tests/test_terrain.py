"""Tests for the destructible terrain."""

from __future__ import annotations

from random import Random

from bummsschloss.world.terrain import Terrain


def flat(width: int = 200, height: int = 300, level: float = 150.0) -> Terrain:
    return Terrain(width, height, [level] * width)


def test_generated_terrain_wraps_seamlessly():
    terrain = Terrain.generate(400, 300, Random(7))
    # The generator uses whole-number frequencies only, so the two ends must
    # line up closely enough for a shot to cross the seam unnoticed.
    assert abs(terrain.height_at(0) - terrain.height_at(399)) < 6.0


def test_generated_terrain_stays_within_bounds():
    terrain = Terrain.generate(400, 300, Random(1))
    for height in terrain.heights():
        assert 0 <= height <= 300


def test_columns_wrap_in_both_directions():
    terrain = flat(width=100)
    terrain.flatten(0, 0, 42.0)
    assert terrain.height_at(-100) == 42.0
    assert terrain.height_at(200) == 42.0
    assert terrain.column(-1) == 99


def test_surface_explosion_digs_a_crater():
    terrain = flat()
    terrain.explode(100, 150, 20)
    assert terrain.height_at(100) > 150.0
    # Far from the blast nothing changed.
    assert terrain.height_at(10) == 150.0


def test_underground_explosion_collapses_the_ceiling():
    """A buried blast must not leave a cave - the roof falls in."""
    terrain = flat()
    terrain.explode(100, 200, 20)
    # The entire 40px-tall bubble was underground, so the surface drops by the
    # full chord length of the circle at that column.
    assert terrain.height_at(100) == 190.0
    assert terrain.is_solid(100, 191.0)
    # And crucially there is no hollow space left behind.
    assert not terrain.is_solid(100, 189.0)


def test_explosions_never_dig_below_the_world_floor():
    terrain = flat(height=160, level=150.0)
    for _ in range(5):
        terrain.explode(50, 155, 30)
    assert terrain.height_at(50) <= 160.0


def test_explosion_wraps_across_the_seam():
    terrain = flat(width=100)
    terrain.explode(0, 150, 10)
    assert terrain.height_at(99) > 150.0
    assert terrain.height_at(1) > 150.0


def test_raise_ground_piles_earth_up():
    terrain = flat()
    terrain.raise_ground(100, 20, 10)
    assert terrain.height_at(100) < 150.0


def test_version_changes_only_on_modification():
    terrain = flat()
    before = terrain.version
    terrain.height_at(10)
    assert terrain.version == before
    terrain.explode(100, 150, 10)
    assert terrain.version > before
