"""Tests for matches with more than two seats."""

from __future__ import annotations

from random import Random

import pytest

from bummsschloss import config
from bummsschloss.match import Match, Phase
from bummsschloss.matchsetup import IncomeModel, MatchSetup


def build(count: int, seed: int = 4242, **kwargs) -> Match:
    return Match(setup=MatchSetup.default(count, **kwargs), seed=seed)


def run_until_aim(match: Match, limit: int = 20000) -> bool:
    for _step in range(limit):
        if match.phase is Phase.AIM:
            return True
        if match.phase is Phase.GAME_OVER:
            return False
        match.update(config.FIXED_DT)
    raise AssertionError("the turn never resolved")


# -- seating -----------------------------------------------------------------


@pytest.mark.parametrize("count", range(config.MIN_PLAYERS, config.MAX_PLAYERS + 1))
def test_every_player_gets_a_castle_on_solid_ground(count):
    match = build(count)
    assert len(match.players) == count
    assert len(match.castles) == count
    for castle in match.castles:
        assert castle.alive
        assert castle.bottom_y == castle.support_level(match.terrain)


@pytest.mark.parametrize("count", range(config.MIN_PLAYERS, config.MAX_PLAYERS + 1))
def test_castles_do_not_overlap_each_other(count):
    """However the dice fall, nobody ends up in their neighbour's moat."""
    for seed in range(20):
        match = build(count, seed=seed)
        centres = sorted(castle.centre_x for castle in match.castles)
        gaps = [right - left for left, right in zip(centres, centres[1:], strict=False)]
        # The world wraps, so the outermost two are neighbours as well.
        gaps.append(match.width - centres[-1] + centres[0])
        assert min(gaps) > config.CASTLE_WIDTH * 1.5, f"seed {seed}, count {count}"


def test_the_castles_move_around_from_match_to_match():
    places = {
        tuple(round(castle.centre_x) for castle in build(3, seed=seed).castles)
        for seed in range(12)
    }
    assert len(places) > 8, "the landscape changes but the castles always stand still"


def test_the_seating_order_is_shuffled_too():
    """Player one must not always be the one on the left."""
    leftmost = {
        min(build(4, seed=seed).castles, key=lambda c: c.centre_x).owner
        for seed in range(25)
    }
    assert len(leftmost) > 1


def test_even_spots_are_still_available_without_an_rng():
    assert config.castle_spots(2) == (0.25, 0.75)
    assert config.castle_spots(4) == (0.125, 0.375, 0.625, 0.875)


def test_jittered_spots_stay_inside_their_own_slot():
    rng = Random(5)
    for _attempt in range(50):
        spots = config.castle_spots(4, rng)
        assert len(set(spots)) == 4
        assert all(0.0 <= spot < 1.0 for spot in spots)


def test_seat_names_and_colours_come_from_the_setup():
    setup = MatchSetup.default(3)
    setup.rename(0, "Ada")
    setup.rename(1, "Bert")
    setup.cycle_color(2)
    match = Match(setup=setup, seed=7)

    assert [p.name for p in match.players[:2]] == ["Ada", "Bert"]
    assert match.players[2].color_index == setup.players[2].color_index
    assert len({p.color_index for p in match.players}) == 3


# -- turn order --------------------------------------------------------------


def test_the_turn_passes_round_the_table():
    match = build(4)
    seen = [match.current_player]
    for _turn in range(3):
        assert match.fire()
        run_until_aim(match)
        seen.append(match.current_player)
    assert seen == [0, 1, 2, 3]


def test_a_destroyed_player_is_skipped():
    match = build(3)
    match.castles[1].hp = 0.0
    assert not match.castles[1].alive

    assert match.fire()
    run_until_aim(match)
    assert match.current_player == 2


def test_the_match_runs_on_while_two_castles_stand():
    match = build(3)
    match.castles[2].hp = 0.0
    match.update(config.FIXED_DT)
    assert match.phase is not Phase.GAME_OVER


def test_the_last_castle_standing_wins():
    match = build(4)
    for index in (1, 2, 3):
        match.castles[index].hp = 0.0

    assert match.fire()
    run_until_aim(match)
    assert match.phase is Phase.GAME_OVER
    assert match.winner == 0
    assert match.summary is not None
    assert len(match.summary.stats) == 4
    assert len(match.summary.color_indices) == 4


def test_living_opponents_excludes_the_dead_and_oneself():
    match = build(4)
    match.castles[2].hp = 0.0
    assert match.living_opponents(0) == [1, 3]


# -- economy -----------------------------------------------------------------


def test_starting_money_comes_from_the_setup():
    setup = MatchSetup.default(3, starting_money=1200, turn_income=100)
    match = Match(setup=setup, seed=7)
    assert match.players[0].money == 1200 + 100
    assert match.players[1].money == 1200
    assert match.players[2].money == 1200


def test_the_round_number_counts_full_trips_round_the_table():
    match = build(3)
    assert match.round_number == 1
    for _turn in range(3):
        assert match.fire()
        run_until_aim(match)
    assert match.round_number == 2


def test_catchup_economy_pays_a_damaged_player_more():
    setup = MatchSetup.default(2, turn_income=200, income_model=IncomeModel.CATCHUP)
    match = Match(setup=setup, seed=7)
    match.castles[1].hp = match.castles[1].max_hp * 0.5
    before = match.players[1].money

    assert match.fire()
    run_until_aim(match)
    assert match.current_player == 1
    assert match.players[1].money - before == 300
