"""Tests for the statistics and the end-of-match awards."""

from __future__ import annotations

from bummsschloss.stats import AWARDS, PlayerStats, award_winners


def test_derived_numbers_handle_a_player_who_never_fired():
    stats = PlayerStats()
    assert stats.accuracy == 0.0
    assert stats.damage_per_shot == 0.0
    assert stats.cost_per_damage == float("inf")


def test_derived_numbers():
    stats = PlayerStats(shots_fired=4, shots_hit=3, damage_dealt=60.0, money_spent=300)
    assert stats.accuracy == 0.75
    assert stats.damage_per_shot == 15.0
    assert stats.cost_per_damage == 5.0


def test_award_goes_to_the_better_player():
    results = award_winners(
        [
            PlayerStats(shots_fired=3, damage_dealt=90.0),
            PlayerStats(shots_fired=3, damage_dealt=30.0),
        ]
    )
    total = next(r for r in results if r.award.key == "total_damage")
    assert total.player_index == 0
    assert total.value == 90.0
    assert total.formatted_value == "90 damage"


def test_ties_are_not_awarded():
    results = award_winners([PlayerStats(damage_dealt=50.0), PlayerStats(damage_dealt=50.0)])
    assert all(r.award.key != "total_damage" for r in results)


def test_awards_nobody_earned_are_skipped():
    results = award_winners([PlayerStats(), PlayerStats()])
    assert results == []


def test_lowest_wins_awards_pick_the_smaller_value():
    thrifty = PlayerStats(damage_dealt=100.0, money_spent=200)   # 2 per point
    spendy = PlayerStats(damage_dealt=100.0, money_spent=900)    # 9 per point
    results = award_winners([thrifty, spendy])
    thrift = next(r for r in results if r.award.key == "thrift")
    assert thrift.player_index == 0


def test_infinite_cost_per_damage_never_wins_an_award():
    """A player who did no damage at all is not a thrifty quartermaster."""
    results = award_winners([PlayerStats(money_spent=500), PlayerStats(money_spent=500)])
    assert all(r.award.key != "thrift" for r in results)


def test_every_award_metric_survives_an_empty_stat_block():
    stats = PlayerStats()
    for award in AWARDS:
        value = award.metric(stats)
        assert isinstance(value, float)


def test_summary_groups_awards_by_player():
    from bummsschloss.stats import MatchSummary

    stats = [PlayerStats(shots_fired=2, damage_dealt=40.0), PlayerStats(shots_fired=2)]
    summary = MatchSummary(
        winner=0,
        turns=5,
        player_names=["Player 1", "Player 2"],
        stats=stats,
        awards=award_winners(stats),
    )
    assert summary.awards_for(0)
    assert not summary.awards_for(1)
