"""Tests for what makes each weapon special."""

from __future__ import annotations

import math

import pytest

from bummsschloss import config
from bummsschloss.match import Match, Phase
from bummsschloss.matchsetup import MatchSetup
from bummsschloss.weapons import ARSENAL, by_key
from bummsschloss.world.projectile import Projectile


@pytest.fixture
def match() -> Match:
    return Match(seed=1234)


def fly(match: Match, limit: int = 20000) -> None:
    """Run the current shot until the turn has resolved."""
    for _step in range(limit):
        if match.phase in (Phase.AIM, Phase.GAME_OVER):
            return
        match.update(config.FIXED_DT)
    raise AssertionError("the shot never resolved")


def launch(match: Match, key: str, *, angle: float, power: float = 0.8) -> None:
    """Fire a specific weapon, affording it if necessary."""
    index = next(i for i, w in enumerate(ARSENAL) if w.key == key)
    match.select_weapon(index)
    match.player.money = max(match.player.money, ARSENAL[index].cost)
    match.player.angle = angle
    match.player.power = power
    assert match.fire()


# -- the arsenal as a whole --------------------------------------------------


def test_every_weapon_explains_itself():
    assert all(weapon.description for weapon in ARSENAL)


def test_the_arsenal_fits_the_number_keys():
    assert len(ARSENAL) <= 9, "the HUD binds weapons to keys 1-9"


def test_weapon_keys_are_unique():
    keys = [weapon.key for weapon in ARSENAL]
    assert len(set(keys)) == len(keys)


def test_the_terrain_raising_weapon_is_gone():
    assert not any(weapon.key == "molehill" for weapon in ARSENAL)


# -- the free dud ------------------------------------------------------------


def test_the_dud_is_free_so_a_player_can_always_act(match):
    dud = by_key("dud")
    assert dud.cost == 0

    match.player.money = 0
    index = next(i for i, w in enumerate(ARSENAL) if w.key == "dud")
    match.select_weapon(index)
    assert match.can_fire()
    assert match.fire()


def test_firing_the_dud_lets_money_accumulate(match):
    before = match.players[0].money
    launch(match, "dud", angle=-80.0)
    assert match.players[0].money == before
    fly(match)
    assert match.players[1].money > 0


def test_the_dud_still_does_a_little_damage():
    dud = by_key("dud")
    assert 0 < dud.damage <= 5


# -- the balloon bomb --------------------------------------------------------


def test_the_balloon_never_falls():
    balloon = by_key("balloon_bomb")
    assert balloon.gravity_scale == 0.0

    shot = Projectile(x=0.0, y=100.0, vx=200.0, vy=0.0, weapon=balloon, owner=0)
    for _step in range(600):
        shot.step(config.FIXED_DT, wind=0.0)
    assert shot.y == pytest.approx(100.0)


def test_the_balloon_is_carried_by_the_wind():
    balloon = by_key("balloon_bomb")
    shot = Projectile(x=0.0, y=100.0, vx=0.0, vy=0.0, weapon=balloon, owner=0)
    for _step in range(120):
        shot.step(config.FIXED_DT, wind=100.0)
    assert shot.vx > 0
    assert shot.x > 0


# -- shots that can never come back ------------------------------------------


@pytest.mark.parametrize("key", ["balloon_bomb", "laser"])
def test_a_gravity_free_shot_fired_upwards_is_given_up_on_quickly(key, match):
    """Without gravity these never fall back, so they must not stall the turn."""
    launch(match, key, angle=-60.0, power=1.0)
    ticks = 0
    while match.phase is Phase.FLIGHT and ticks < 40000:
        match.update(config.FIXED_DT)
        ticks += 1

    elapsed = ticks * config.FIXED_DT
    assert elapsed < config.MAX_FLIGHT_TIME / 2, f"{key} took {elapsed:.1f}s"
    assert match.last_event == "The shot was lost in the clouds."


def test_a_shot_that_is_still_climbing_in_view_is_left_alone(match):
    """The early write-off must not touch a shot that is still on screen."""
    launch(match, "balloon_bomb", angle=-10.0, power=0.5)
    shot = match.projectiles[0]
    shot.y = 50.0
    assert not match._gone_for_good(shot)


def test_an_ordinary_shot_above_the_screen_keeps_flying(match):
    """Gravity will bring it back, so it must not be written off."""
    launch(match, "cannonball", angle=-85.0, power=1.0)
    shot = match.projectiles[0]
    shot.y = -2000.0
    assert not match._gone_for_good(shot)


# -- the laser ---------------------------------------------------------------


def test_the_laser_flies_dead_straight():
    laser = by_key("laser")
    assert laser.gravity_scale == 0.0
    assert laser.wdabhkt == 0.0

    shot = Projectile(x=0.0, y=200.0, vx=300.0, vy=-400.0, weapon=laser, owner=0)
    start = (shot.x, shot.y)
    for _step in range(60):
        shot.step(config.FIXED_DT, wind=config.WIND_MAX)

    # Every sample must sit on the straight line through the start point.
    direction = math.atan2(-400.0, 300.0)
    for x, y in shot.trail:
        assert math.atan2(y - start[1], x - start[0]) == pytest.approx(direction, abs=1e-6)


def test_the_laser_does_not_care_about_the_wind():
    """A gale must not shift the laser off its line by a single pixel."""
    laser = by_key("laser")
    calm = Projectile(x=0.0, y=200.0, vx=300.0, vy=-400.0, weapon=laser, owner=0)
    gale = Projectile(x=0.0, y=200.0, vx=300.0, vy=-400.0, weapon=laser, owner=0)

    for _step in range(60):
        calm.step(config.FIXED_DT, wind=0.0)
        gale.step(config.FIXED_DT, wind=config.WIND_MAX)

    assert gale.x == pytest.approx(calm.x)
    assert gale.y == pytest.approx(calm.y)


# -- the mole ----------------------------------------------------------------


def test_the_mole_digs_through_the_ground_instead_of_stopping(match):
    mole = by_key("mole")
    assert mole.burrows

    surface = match.terrain.height_at(300)
    shot = Projectile(
        x=300.0, y=surface - 2.0, vx=0.0, vy=300.0, weapon=mole, owner=0
    )
    match.projectiles = [shot]
    match.phase = Phase.FLIGHT
    match._shot_owner = 0

    for _step in range(6):
        match.update(config.FIXED_DT)
        if shot.burrowing:
            break
    assert shot.burrowing, "the mole should bite into the hill"

    depth_before = shot.y
    for _step in range(20):
        match.update(config.FIXED_DT)
        if not match.projectiles:
            break
    assert shot.y > depth_before, "the mole should keep going down into the earth"


def test_the_mole_detonates_once_its_tunnel_runs_out(match):
    """It may pop in and out of the ground, but the budget only ever shrinks."""
    before = [match.terrain.height_at(x) for x in range(0, match.width, 5)]
    shot = Projectile(x=300.0, y=match.terrain.height_at(300) - 2.0, vx=0.0, vy=300.0,
                      weapon=by_key("mole"), owner=0)
    match.projectiles = [shot]
    match.phase = Phase.FLIGHT
    match._shot_owner = 0

    fly(match)
    assert not match.projectiles
    after = [match.terrain.height_at(x) for x in range(0, match.width, 5)]
    assert any(now > then for now, then in zip(after, before, strict=True)), "it left no crater"


def test_a_burrowing_round_keeps_a_steady_pace():
    mole = by_key("mole")
    shot = Projectile(x=0.0, y=0.0, vx=600.0, vy=0.0, weapon=mole, owner=0)
    shot.start_burrowing()
    shot.step(config.FIXED_DT, wind=config.WIND_MAX)
    assert math.hypot(shot.vx, shot.vy) == pytest.approx(mole.burrow_speed)


def test_the_mole_noses_upwards_while_it_digs():
    """The dig is a cannon shot in reverse: it steers back towards daylight."""
    mole = by_key("mole")
    shot = Projectile(x=0.0, y=0.0, vx=0.0, vy=mole.burrow_speed, weapon=mole, owner=0)
    shot.start_burrowing()
    for _step in range(int(1.0 / config.FIXED_DT)):
        shot.step(config.FIXED_DT, wind=0.0)
    assert shot.vy < 0.0, "after a second of digging it should be heading up again"


def test_the_mole_breaks_back_out_of_the_hill(match):
    """Fired into a slope it must reappear rather than sulk underground."""
    mole = by_key("mole")
    surface = match.terrain.height_at(300)
    shot = Projectile(x=300.0, y=surface - 2.0, vx=120.0, vy=260.0, weapon=mole, owner=0)
    match.projectiles = [shot]
    match.phase = Phase.FLIGHT
    match._shot_owner = 0

    dug = False
    surfaced = False
    for _step in range(20000):
        match.update(config.FIXED_DT)
        if not match.projectiles:
            break
        dug = dug or shot.burrowing
        if dug and not shot.burrowing:
            surfaced = True
            break
    assert dug, "it never entered the ground"
    assert surfaced, "it never came back up"


def test_a_surfaced_mole_keeps_the_rest_of_its_tunnel(match):
    """Coming up for air must not refill - or reset - the digging budget."""
    mole = by_key("mole")
    shot = Projectile(x=0.0, y=0.0, vx=0.0, vy=200.0, weapon=mole, owner=0)
    shot.start_burrowing()
    shot.step(config.FIXED_DT, wind=0.0)
    left = shot.burrow_left
    assert left < mole.burrow_depth

    shot.stop_burrowing()
    assert shot.burrow_left == left
    assert shot.can_burrow


def test_the_mole_flies_through_the_castle_of_whoever_fired_it(match):
    """Aiming down at your own feet is the point of the weapon."""
    assert by_key("mole").ignores_own_castle
    castle = match.castles[0]
    start = (castle.centre_x - 60, castle.top_y + 10)
    end = (castle.centre_x + 60, castle.top_y + 10)

    mine = Projectile(x=start[0], y=start[1], vx=400.0, vy=0.0, weapon=by_key("mole"), owner=0)
    assert match._impact_point(start, end, mine) is None


def test_the_mole_of_an_opponent_still_hits_that_castle(match):
    castle = match.castles[0]
    start = (castle.centre_x - 60, castle.top_y + 10)
    end = (castle.centre_x + 60, castle.top_y + 10)

    theirs = Projectile(x=start[0], y=start[1], vx=400.0, vy=0.0, weapon=by_key("mole"), owner=1)
    assert match._impact_point(start, end, theirs) is not None


def test_an_ordinary_round_still_hits_the_castle_that_fired_it(match):
    """The exemption is the mole's alone."""
    castle = match.castles[0]
    start = (castle.centre_x - 60, castle.top_y + 10)
    end = (castle.centre_x + 60, castle.top_y + 10)

    own = Projectile(
        x=start[0], y=start[1], vx=400.0, vy=0.0, weapon=by_key("cannonball"), owner=0
    )
    assert match._impact_point(start, end, own) is not None


def test_the_mole_still_stops_at_a_castle(match):
    mole = by_key("mole")
    castle = match.castles[1]
    shot = Projectile(
        x=castle.centre_x - 40,
        y=castle.top_y + 10,
        vx=400.0,
        vy=0.0,
        weapon=mole,
        owner=0,
    )
    match.projectiles = [shot]
    match.phase = Phase.FLIGHT
    match._shot_owner = 0
    before = castle.hp

    fly(match)
    assert castle.hp < before


# -- the earthquake ----------------------------------------------------------


def test_the_earthquake_hits_every_castle_by_the_same_amount():
    setup = MatchSetup.default(4)
    match = Match(setup=setup, seed=77)
    quake = by_key("earthquake")
    before = [castle.hp for castle in match.castles]

    launch(match, "earthquake", angle=-80.0, power=0.3)
    fly(match)

    dealt = [b - c.hp for b, c in zip(before, match.castles, strict=True)]
    assert all(d == pytest.approx(quake.damage) for d in dealt), dealt


def test_the_earthquake_hurts_the_shooter_too():
    match = Match(setup=MatchSetup.default(3), seed=77)
    launch(match, "earthquake", angle=-80.0, power=0.3)
    fly(match)
    assert match.players[0].stats.self_damage > 0
    assert match.players[0].stats.damage_dealt > 0


def test_the_earthquake_ignores_distance():
    """Distance must not matter, so the far castle suffers as much as the near one."""
    match = Match(setup=MatchSetup.default(2), seed=77)
    before = [castle.hp for castle in match.castles]
    launch(match, "earthquake", angle=-80.0, power=0.3)
    fly(match)
    dealt = [b - c.hp for b, c in zip(before, match.castles, strict=True)]
    assert dealt[0] == pytest.approx(dealt[1])


def test_the_earthquake_barely_scratches_the_ground():
    quake = by_key("earthquake")
    assert quake.crater_radius < quake.blast_radius


def test_a_dead_castle_is_not_shaken_again():
    match = Match(setup=MatchSetup.default(3), seed=77)
    match.castles[2].hp = 0.0
    launch(match, "earthquake", angle=-80.0, power=0.3)
    fly(match)
    assert match.castles[2].hp == 0.0
