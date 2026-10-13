"""Tests for the pre-match choices: seats, names, colours and the economy."""

from __future__ import annotations

import pytest

from bummsschloss import config
from bummsschloss.matchsetup import DEFAULT_NAMES, MAX_NAME_LENGTH, IncomeModel, MatchSetup

# -- seats -------------------------------------------------------------------


def test_a_fresh_setup_seats_the_minimum_number_of_players():
    setup = MatchSetup()
    assert setup.player_count == config.MIN_PLAYERS
    assert [p.name for p in setup.players] == list(DEFAULT_NAMES[: config.MIN_PLAYERS])


@pytest.mark.parametrize("count", range(config.MIN_PLAYERS, config.MAX_PLAYERS + 1))
def test_every_allowed_player_count_gets_distinct_colours(count):
    setup = MatchSetup.default(count)
    assert setup.player_count == count
    colors = [player.color_index for player in setup.players]
    assert len(set(colors)) == count


def test_the_player_count_is_clamped_to_the_allowed_range():
    setup = MatchSetup()
    setup.set_player_count(99)
    assert setup.player_count == config.MAX_PLAYERS
    setup.set_player_count(0)
    assert setup.player_count == config.MIN_PLAYERS


def test_shrinking_and_growing_keeps_the_existing_seats():
    setup = MatchSetup.default(4)
    setup.rename(1, "Hilde")
    setup.set_player_count(2)
    setup.set_player_count(4)
    assert setup.players[1].name == "Hilde"
    assert len({p.color_index for p in setup.players}) == 4


# -- names -------------------------------------------------------------------


def test_names_are_capped_so_the_hud_cannot_overflow():
    setup = MatchSetup()
    setup.rename(0, "x" * 50)
    assert len(setup.players[0].name) == MAX_NAME_LENGTH


def test_an_empty_name_falls_back_to_the_default():
    setup = MatchSetup()
    setup.rename(0, "   ")
    assert setup.display_name(0) == DEFAULT_NAMES[0]


# -- colours -----------------------------------------------------------------


def test_cycling_a_colour_skips_the_ones_already_taken():
    setup = MatchSetup.default(3)
    others = {setup.players[1].color_index, setup.players[2].color_index}
    for _step in range(len(config.PLAYER_PALETTE) * 2):
        setup.cycle_color(0)
        assert setup.players[0].color_index not in others


def test_cycling_backwards_also_works():
    setup = MatchSetup.default(2)
    start = setup.players[0].color_index
    setup.cycle_color(0, 1)
    setup.cycle_color(0, -1)
    assert setup.players[0].color_index == start


# -- economy options ---------------------------------------------------------


def test_money_options_cycle_through_the_offered_values():
    setup = MatchSetup(starting_money=config.STARTING_MONEY_CHOICES[0])
    setup.cycle_starting_money(1)
    assert setup.starting_money == config.STARTING_MONEY_CHOICES[1]
    setup.cycle_starting_money(-1)
    assert setup.starting_money == config.STARTING_MONEY_CHOICES[0]
    setup.cycle_starting_money(-1)
    assert setup.starting_money == config.STARTING_MONEY_CHOICES[-1]


def test_an_off_list_value_snaps_to_the_nearest_offered_one():
    setup = MatchSetup(starting_money=610)
    setup.cycle_starting_money(1)
    nearest = config.STARTING_MONEY_CHOICES.index(600)
    assert setup.starting_money == config.STARTING_MONEY_CHOICES[nearest + 1]


def test_income_model_cycles_through_every_model():
    setup = MatchSetup()
    seen = set()
    for _step in range(len(IncomeModel)):
        seen.add(setup.income_model)
        setup.cycle_income_model(1)
    assert seen == set(IncomeModel)


# -- income ------------------------------------------------------------------


def test_flat_income_ignores_round_and_health():
    setup = MatchSetup(turn_income=250, income_model=IncomeModel.FLAT)
    assert setup.income_for(round_number=1, health_fraction=1.0) == 250
    assert setup.income_for(round_number=9, health_fraction=0.1) == 250


def test_rising_income_grows_with_the_rounds():
    setup = MatchSetup(turn_income=200, income_model=IncomeModel.RISING)
    first = setup.income_for(round_number=1, health_fraction=1.0)
    later = setup.income_for(round_number=5, health_fraction=1.0)
    assert first == 200
    assert later > first


def test_catchup_income_pays_the_battered_player_more():
    setup = MatchSetup(turn_income=200, income_model=IncomeModel.CATCHUP)
    healthy = setup.income_for(round_number=3, health_fraction=1.0)
    wounded = setup.income_for(round_number=3, health_fraction=0.0)
    assert healthy == 200
    assert wounded == 400


def test_income_never_goes_negative_on_odd_input():
    setup = MatchSetup(turn_income=100, income_model=IncomeModel.CATCHUP)
    assert setup.income_for(round_number=0, health_fraction=2.0) == 100
    assert setup.income_for(round_number=-3, health_fraction=-1.0) == 200
