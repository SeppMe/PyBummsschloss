"""Per-player statistics and the end-of-match awards.

The rules engine funnels every point of damage through
:meth:`bummsschloss.match.Match._apply_damage`, which updates the shooter's
:class:`PlayerStats`. Once the match is over, :func:`award_winners` turns those
numbers into a handful of titles for the summary screen.

Award ``title`` and ``description`` strings are English source strings and are
run through ``_()`` when displayed.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field


@dataclass
class PlayerStats:
    """Everything we remember about how one player played."""

    shots_fired: int = 0
    #: Shots that hurt an opponent (a cluster round counts once).
    shots_hit: int = 0
    #: Shots that hit nothing at all - no damage to anybody.
    shots_wasted: int = 0

    damage_dealt: float = 0.0
    #: Damage done to one's own castle. Embarrassing, but worth a medal.
    self_damage: float = 0.0
    #: Most damage dealt to opponents by a single fired shot.
    best_shot: float = 0.0
    #: Damage caused indirectly, by undermining a castle so that it falls.
    collapse_damage: float = 0.0

    kills: int = 0
    self_destructs: int = 0

    money_spent: int = 0
    #: Rough amount of landscape rearranged, in pixels of column height.
    terrain_moved: float = 0.0

    @property
    def accuracy(self) -> float:
        """Share of shots that drew blood, between 0 and 1."""
        return self.shots_hit / self.shots_fired if self.shots_fired else 0.0

    @property
    def damage_per_shot(self) -> float:
        """Average damage dealt to opponents per shot fired."""
        return self.damage_dealt / self.shots_fired if self.shots_fired else 0.0

    @property
    def cost_per_damage(self) -> float:
        """Money spent per point of damage; lower is thriftier."""
        return self.money_spent / self.damage_dealt if self.damage_dealt else float("inf")


@dataclass(frozen=True)
class Award:
    """A title handed out at the end of a match."""

    key: str
    title: str
    description: str
    #: Pulls the number this award ranks players by out of their stats.
    metric: Callable[[PlayerStats], float]
    #: How the number is shown next to the winner's name.
    fmt: str = "{:.0f}"
    #: Awards with a higher value win; set False for "lowest wins" awards.
    higher_is_better: bool = True
    #: Ties and zero scores are skipped unless the award allows them.
    minimum: float = 0.000001


@dataclass
class AwardResult:
    """One award together with the player who earned it."""

    award: Award
    player_index: int
    value: float

    @property
    def formatted_value(self) -> str:
        return self.award.fmt.format(self.value)


#: The awards handed out after every match, in display order.
AWARDS: tuple[Award, ...] = (
    Award(
        key="total_damage",
        title="Master Gunner",
        description="greatest total damage",
        metric=lambda s: s.damage_dealt,
        fmt="{:.0f} damage",
    ),
    Award(
        key="best_shot",
        title="Lucky Shot",
        description="greatest damage from a single shot",
        metric=lambda s: s.best_shot,
        fmt="{:.0f} damage",
    ),
    Award(
        key="damage_per_shot",
        title="Model of Efficiency",
        description="greatest average damage per shot",
        metric=lambda s: s.damage_per_shot,
        fmt="{:.1f} per shot",
    ),
    Award(
        key="kills",
        title="Castle Breaker",
        description="most castles destroyed",
        metric=lambda s: float(s.kills),
        fmt="{:.0f}",
    ),
    Award(
        key="accuracy",
        title="Eagle Eye",
        description="best hit rate",
        metric=lambda s: s.accuracy,
        fmt="{:.0%}",
    ),
    Award(
        key="collapse",
        title="Master Sapper",
        description="most damage from collapsing castles",
        metric=lambda s: s.collapse_damage,
        fmt="{:.0f} damage",
    ),
    Award(
        key="terrain",
        title="Landscape Gardener",
        description="most earth moved",
        metric=lambda s: s.terrain_moved,
        fmt="{:.0f} shovelfuls",
    ),
    Award(
        key="wasted",
        title="Cloud Hunter",
        description="most shots that hit nothing",
        metric=lambda s: float(s.shots_wasted),
        fmt="{:.0f} shots",
    ),
    Award(
        key="self_damage",
        title="Own Goal",
        description="most damage to one's own castle",
        metric=lambda s: s.self_damage,
        fmt="{:.0f} damage",
    ),
    Award(
        key="thrift",
        title="Thrifty Quartermaster",
        description="least money spent per point of damage",
        metric=lambda s: s.cost_per_damage,
        fmt="{:.0f} coins per point",
        higher_is_better=False,
    ),
)


def award_winners(stats: Sequence[PlayerStats]) -> list[AwardResult]:
    """Work out who earned which award.

    Awards nobody qualifies for, and awards that end in a tie, are left out -
    a shared medal is no fun to read on a summary screen.
    """
    results: list[AwardResult] = []
    for award in AWARDS:
        values = [award.metric(entry) for entry in stats]
        usable = [v for v in values if _is_meaningful(v, award)]
        if not usable:
            continue
        best = max(usable) if award.higher_is_better else min(usable)
        winners = [i for i, v in enumerate(values) if v == best and _is_meaningful(v, award)]
        if len(winners) != 1:
            continue
        results.append(AwardResult(award=award, player_index=winners[0], value=best))
    return results


def _is_meaningful(value: float, award: Award) -> bool:
    """Filter out zero scores and the infinities we use for "never scored"."""
    if value != value or value in (float("inf"), float("-inf")):  # NaN / inf
        return False
    return value >= award.minimum


@dataclass
class MatchSummary:
    """Everything the post-game screen needs."""

    winner: int | None
    turns: int
    player_names: list[str] = field(default_factory=list)
    stats: list[PlayerStats] = field(default_factory=list)
    awards: list[AwardResult] = field(default_factory=list)

    def awards_for(self, player_index: int) -> list[AwardResult]:
        return [r for r in self.awards if r.player_index == player_index]
