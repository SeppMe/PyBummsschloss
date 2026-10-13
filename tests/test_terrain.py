"""Tests for the destructible terrain."""

from __future__ import annotations

from random import Random

from bummsschloss.world.terrain import MAX_PEAKS, Terrain


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


def test_the_landscape_flows_instead_of_rippling():
    """No frilly saw teeth: neighbouring columns stay close together."""
    for seed in range(12):
        heights = Terrain.generate(960, 540, Random(seed)).heights()
        steepest = max(
            abs(heights[(x + 1) % 960] - heights[x]) for x in range(960)
        )
        assert steepest < 6.0, f"seed {seed} is too jagged: {steepest:.1f} px per column"


def test_the_landscape_has_a_handful_of_big_hills():
    """One to three major peaks, not a field of waves."""
    reach = 70
    for seed in range(12):
        heights = Terrain.generate(960, 540, Random(seed)).heights()
        peaks = sum(
            1
            for x in range(960)
            if all(heights[x] <= heights[(x + d) % 960] for d in range(-reach, reach + 1))
        )
        assert 1 <= peaks <= MAX_PEAKS, f"seed {seed} has {peaks} peaks"


def test_the_landscape_is_not_flat():
    heights = Terrain.generate(960, 540, Random(3)).heights()
    assert max(heights) - min(heights) > 540 * 0.4


def test_an_apron_eases_a_plateau_into_the_hillside():
    terrain = Terrain(200, 300, [100.0 + x for x in range(200)])
    terrain.flatten(90, 110, 150.0, blend=20)

    assert terrain.height_at(100) == 150.0
    # Just outside the plateau the ground leans towards the new level, and
    # further out it is back to the untouched slope.
    assert 150.0 < terrain.height_at(115) < 215.0
    assert terrain.height_at(150) == 250.0


def test_the_average_surface_sits_between_the_extremes():
    terrain = Terrain(100, 300, [100.0] * 50 + [200.0] * 50)
    assert terrain.average_surface(40, 59) == 150.0


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


def test_version_changes_only_on_modification():
    terrain = flat()
    before = terrain.version
    terrain.height_at(10)
    assert terrain.version == before
    terrain.explode(100, 150, 10)
    assert terrain.version > before
