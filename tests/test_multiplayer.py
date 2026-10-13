"""Tests for matches with more than two seats."""

from __future__ import annotations

import pytest

from bummsschloss import config
from bummsschloss.match import Match, Phase
from bummsschloss.matchsetup import IncomeModel, MatchSetup


def build(count: int, **kwargs) -> Match:
    return Match(setup=MatchSetup.default(count, **kwargs), seed=4242)


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
    match = build(count)
    centres = sorted(castle.centre_x for castle in match.castles)
    for left, right in zip(centres, centres[1:], strict=False):
        assert right - left > config.CASTLE_WIDTH


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
