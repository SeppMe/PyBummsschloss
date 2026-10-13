"""Tests for the rules engine: turns, economy, wind, physics and stats."""

from __future__ import annotations

import math

import pytest

from bummsschloss import config
from bummsschloss.match import Match, Phase
from bummsschloss.weapons import ARSENAL, by_key


@pytest.fixture
def match() -> Match:
    return Match(seed=1234)


def run_until_aim(match: Match, limit: int = 20000) -> bool:
    """Advance the match until the next player may aim again."""
    for _ in range(limit):
        if match.phase is Phase.AIM:
            return True
        if match.phase is Phase.GAME_OVER:
            return False
        match.update(config.FIXED_DT)
    raise AssertionError("the turn never resolved")


# -- setup -------------------------------------------------------------------


def test_match_starts_with_two_seated_castles(match):
    assert len(match.castles) == 2
    for castle in match.castles:
        assert castle.bottom_y == castle.support_level(match.terrain)
        assert castle.alive


def test_same_seed_produces_the_same_landscape():
    assert Match(seed=99).terrain.heights() == Match(seed=99).terrain.heights()


def test_starting_player_receives_income(match):
    assert match.players[0].money == config.STARTING_MONEY + config.TURN_INCOME
    assert match.players[1].money == config.STARTING_MONEY


# -- turns and economy -------------------------------------------------------


def test_firing_costs_money_and_switches_player(match):
    before = match.players[0].money
    weapon = match.player.weapon

    assert match.fire()
    assert match.players[0].money == before - weapon.cost
    assert match.phase is Phase.FLIGHT

    run_until_aim(match)
    assert match.current_player == 1
    assert match.players[1].money == config.STARTING_MONEY + config.TURN_INCOME


def test_cannot_fire_an_unaffordable_weapon(match):
    match.select_weapon(len(ARSENAL) - 1)  # the expensive one
    match.player.money = 0
    assert not match.can_fire()
    assert not match.fire()
    assert match.phase is Phase.AIM


def test_cannot_fire_while_a_shot_is_in_the_air(match):
    assert match.fire()
    assert not match.fire()


def test_wind_is_redrawn_every_turn(match):
    winds = {match.wind}
    for _ in range(6):
        match.fire()
        if not run_until_aim(match):
            break
        winds.add(match.wind)
    assert len(winds) > 1
    assert all(abs(w) <= config.WIND_MAX for w in winds)


# -- physics -----------------------------------------------------------------


def test_wdabhkt_decides_how_far_the_wind_pushes_a_shot():
    """Same shot, same wind - only the wind coefficient differs."""
    from bummsschloss.world.projectile import Projectile

    heavy = by_key("cannonball")
    light = by_key("balloon_bomb")
    assert light.wdabhkt > heavy.wdabhkt

    drifts = []
    for weapon in (heavy, light):
        shot = Projectile(x=0.0, y=0.0, vx=0.0, vy=0.0, weapon=weapon, owner=0)
        for _ in range(240):
            shot.step(config.FIXED_DT, wind=config.WIND_MAX)
        drifts.append(shot.x)

    assert drifts[1] > drifts[0] > 0


def test_gravity_scale_decides_how_fast_a_shot_drops():
    from bummsschloss.world.projectile import Projectile

    mortar = by_key("mortar")
    cannonball = by_key("cannonball")

    falls = []
    for weapon in (mortar, cannonball):
        shot = Projectile(x=0.0, y=0.0, vx=0.0, vy=0.0, weapon=weapon, owner=0)
        for _index in range(120):
            shot.step(config.FIXED_DT, wind=0.0)
        falls.append(shot.y)

    assert falls[0] > falls[1] > 0


def test_shots_keep_flying_past_the_right_edge(match):
    """Leaving the right edge is not a collision - the shot keeps going."""
    match.fire()
    shot = match.projectiles[0]
    shot.x = match.width - 10.0
    shot.y = -400.0  # well above the screen, so nothing can be hit
    shot.vx = 600.0
    shot.vy = -200.0

    for _ in range(60):
        match.update(config.FIXED_DT)
    assert match.projectiles, "the shot should still be in the air"
    assert match.projectiles[0].x > match.width
    # The wrapped position is what collision and drawing use.
    assert 0 <= match.terrain.wrap_x(match.projectiles[0].x) < match.width


def test_an_impact_past_the_right_edge_lands_on_the_left(match):
    """A crater dug at x = width + 100 must appear at column 100."""
    match.fire()
    shot = match.projectiles[0]
    shot.x = match.width + 100.0
    shot.y = match.terrain.height_at(100) - 20.0
    shot.vx = 0.0
    shot.vy = 200.0

    before = match.terrain.height_at(100)
    while match.phase is Phase.FLIGHT:
        match.update(config.FIXED_DT)

    assert match.terrain.height_at(100) != before
    assert match.explosions
    assert 0 <= match.explosions[0].x < match.width


def test_a_shot_fired_straight_up_still_comes_down(match):
    """Leaving the top of the screen is not an escape."""
    match.player.angle = -90.0
    match.player.power = 1.0
    match.fire()

    went_above_the_screen = False
    for _ in range(20000):
        match.update(config.FIXED_DT)
        if match.projectiles and match.projectiles[0].y < 0:
            went_above_the_screen = True
        if match.phase is not Phase.FLIGHT:
            break
    assert went_above_the_screen
    assert not match.projectiles


def test_endless_shots_are_given_up_on(match):
    """A shot that never lands must not stall the game forever."""
    match.fire()
    shot = match.projectiles[0]
    shot.age = config.MAX_FLIGHT_TIME
    match.update(config.FIXED_DT)
    assert not match.projectiles
    assert match.last_event == "The shot was lost in the clouds."


def test_cluster_weapon_splits_into_bomblets(match):
    index = next(i for i, w in enumerate(ARSENAL) if w.is_cluster)
    match.select_weapon(index)
    match.player.money = 10000
    match.player.angle = -70.0
    match.fire()

    most = 0
    for _ in range(6000):
        match.update(config.FIXED_DT)
        most = max(most, len(match.projectiles))
        if match.phase is not Phase.FLIGHT:
            break
    assert most >= ARSENAL[index].submunitions


# -- damage and statistics ---------------------------------------------------


def hit_the_enemy(match: Match) -> None:
    """Drop a shot straight onto the opposing castle and let the turn resolve.

    Per-shot bookkeeping (hits, best shot, wasted shots) is only finalised once
    the dust has settled, because a collapse can still change the outcome.
    """
    target = match.castles[match.opponent_of(match.current_player)]
    match.fire()
    shot = match.projectiles[0]
    shot.x = target.centre_x
    shot.y = target.top_y - 2
    shot.vy = 200.0
    shot.vx = 0.0
    run_until_aim(match)


def miss_everything(match: Match) -> None:
    """Fire a shot that lands in no-man's-land between the castles."""
    match.fire()
    shot = match.projectiles[0]
    shot.x = match.width / 2
    shot.y = match.terrain.height_at(match.width / 2) - 30.0
    shot.vx = 0.0
    shot.vy = 200.0
    run_until_aim(match)


def test_a_hit_is_recorded_for_the_shooter(match):
    shooter = match.player
    hit_the_enemy(match)
    stats = shooter.stats
    assert stats.shots_fired == 1
    assert stats.shots_hit == 1
    assert stats.damage_dealt > 0
    assert stats.best_shot == pytest.approx(stats.damage_dealt)
    assert stats.shots_wasted == 0


def test_a_miss_counts_as_a_wasted_shot(match):
    shooter = match.player
    miss_everything(match)
    assert shooter.stats.shots_wasted == 1
    assert shooter.stats.shots_hit == 0
    assert shooter.stats.damage_dealt == 0


def test_damage_to_your_own_castle_is_tracked_separately(match):
    shooter = match.player
    own = match.castles[match.current_player]
    match.fire()
    shot = match.projectiles[0]
    shot.x, shot.y = own.centre_x, own.top_y + 2
    shot.vy = 50.0
    while match.phase is Phase.FLIGHT:
        match.update(config.FIXED_DT)

    assert shooter.stats.self_damage > 0
    assert shooter.stats.damage_dealt == 0


def test_terrain_moved_is_credited_to_the_shooter(match):
    shooter = match.player
    match.player.angle = -45.0
    match.player.power = 0.3
    match.fire()
    run_until_aim(match)
    assert shooter.stats.terrain_moved > 0


def test_collapse_damage_is_credited_to_whoever_dug(match):
    """Undermining the enemy counts as your damage, not an act of god."""
    shooter = match.current_player
    victim = match.castles[match.opponent_of(shooter)]
    match.fire()
    match.projectiles.clear()
    # Pull the rug out from under the enemy castle while the turn resolves.
    match.terrain.flatten(int(victim.left), int(victim.right), victim.bottom_y + 120)
    match.phase = Phase.SETTLE

    run_until_aim(match)
    stats = match.players[shooter].stats
    assert stats.collapse_damage > 0
    assert stats.damage_dealt >= stats.collapse_damage


def test_destroying_a_castle_ends_the_match_and_builds_a_summary(match):
    shooter = match.current_player
    victim = match.castles[match.opponent_of(shooter)]
    victim.hp = 1.0

    hit_the_enemy(match)
    for _ in range(5000):
        if match.phase is Phase.GAME_OVER:
            break
        match.update(config.FIXED_DT)

    assert match.phase is Phase.GAME_OVER
    assert match.winner == shooter
    assert match.players[shooter].stats.kills == 1

    summary = match.summary
    assert summary is not None
    assert summary.winner == shooter
    assert {result.award.key for result in summary.awards}
    assert all(0 <= result.player_index < 2 for result in summary.awards)


def test_reset_clears_the_statistics(match):
    hit_the_enemy(match)
    match.reset()
    assert all(p.stats.shots_fired == 0 for p in match.players)
    assert match.summary is None
    assert match.phase is Phase.AIM


def test_aiming_handles_the_wrapping_seam(match):
    match.current_player = 0
    # A target just off the left edge is "behind" the left-hand castle.
    match.aim_at(-20.0, match.castle.muzzle[1])
    assert math.isclose(abs(match.player.angle), 180.0, abs_tol=1.0)
