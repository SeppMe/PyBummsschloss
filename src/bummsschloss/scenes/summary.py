"""The post-match screen: who won, how they played, and who earned what.

The numbers come straight from :class:`bummsschloss.stats.MatchSummary`, which
the rules engine fills in the moment a castle falls.
"""

from __future__ import annotations

import pygame

from bummsschloss import config
from bummsschloss.i18n import gettext as _
from bummsschloss.match import Match
from bummsschloss.resources import load_font
from bummsschloss.scenes.base import Scene
from bummsschloss.stats import MatchSummary, PlayerStats

#: Rows of the comparison table: label, value template, and which direction
#: counts as "better" when highlighting the stronger of the two numbers.
STAT_ROWS: tuple[tuple[str, str, str | None], ...] = (
    ("shots fired", "{0.shots_fired:d}", None),
    ("hits", "{0.shots_hit:d}", "max"),
    ("hit rate", "{0.accuracy:.0%}", "max"),
    ("damage dealt", "{0.damage_dealt:.0f}", "max"),
    ("damage per shot", "{0.damage_per_shot:.1f}", "max"),
    ("best single shot", "{0.best_shot:.0f}", "max"),
    ("collapse damage", "{0.collapse_damage:.0f}", "max"),
    ("damage to own castle", "{0.self_damage:.0f}", None),
    ("castles destroyed", "{0.kills:d}", "max"),
    ("money spent", "{0.money_spent:d}", None),
    ("earth moved", "{0.terrain_moved:.0f}", None),
)


class SummaryScene(Scene):
    """Shows the final score sheet and waits for a rematch or a quit."""

    def __init__(self, app, match: Match) -> None:
        super().__init__(app)
        self.match = match
        self.summary: MatchSummary = match.summary or match.build_summary()

    def on_enter(self) -> None:
        self.font = load_font(15)
        self.small_font = load_font(13)
        self.title_font = load_font(34)
        self.award_font = load_font(17)

    # -- input --------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_ESCAPE, pygame.K_q):
            self.app.quit()
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_n):
            from bummsschloss.scenes.match import MatchScene

            self.match.reset(seed=None)
            self.app.replace_scene(MatchScene(self.app, self.match))

    # -- drawing ------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(config.SKY)
        self._draw_title(surface)
        self._draw_table(surface)
        self._draw_awards(surface)

        prompt = self.font.render(
            _("Enter for a rematch   -   Esc to quit"), True, config.GREY
        )
        surface.blit(
            prompt,
            (surface.get_width() // 2 - prompt.get_width() // 2, surface.get_height() - 28),
        )

    def _player_color(self, index: int):
        return config.PLAYER_COLORS[index % len(config.PLAYER_COLORS)]

    def _draw_title(self, surface: pygame.Surface) -> None:
        summary = self.summary
        if summary.winner is None:
            text = _("Everyone lost.")
            color = config.GREY
        else:
            name = _(summary.player_names[summary.winner])
            text = _("{player} wins!").format(player=name)
            color = self._player_color(summary.winner)

        title = self.title_font.render(text, True, color)
        surface.blit(title, (surface.get_width() // 2 - title.get_width() // 2, 24))

        subtitle = self.small_font.render(
            _("{turns} turns").format(turns=summary.turns), True, config.GREY
        )
        surface.blit(subtitle, (surface.get_width() // 2 - subtitle.get_width() // 2, 64))

    def _draw_table(self, surface: pygame.Surface) -> None:
        summary = self.summary
        top = 96
        label_right = 300
        columns = (360, 520)

        for index, name in enumerate(summary.player_names):
            header = self.font.render(_(name), True, self._player_color(index))
            surface.blit(header, (columns[index], top))
        pygame.draw.line(
            surface, config.GREY, (40, top + 20), (columns[-1] + 120, top + 20), 1
        )

        for row, (label, template, better) in enumerate(STAT_ROWS):
            y = top + 28 + row * 19
            text = self.small_font.render(_(label), True, config.WHITE)
            surface.blit(text, (label_right - text.get_width(), y))
            best = self._best_index(template, better)
            for index, entry in enumerate(summary.stats):
                value = template.format(entry)
                color = config.ACCENT if index == best else config.WHITE
                surface.blit(self.small_font.render(value, True, color), (columns[index], y))

    def _best_index(self, template: str, better: str | None) -> int | None:
        """Highlight the better of the two numbers in a row, if there is one."""
        if better is None:
            return None
        values = [self._numeric(template, entry) for entry in self.summary.stats]
        if any(v is None for v in values):
            return None
        best = max(values) if better == "max" else min(values)
        if values.count(best) != 1 or best == 0:
            return None
        return values.index(best)

    @staticmethod
    def _numeric(template: str, entry: PlayerStats) -> float | None:
        text = template.format(entry).rstrip("%")
        try:
            return float(text)
        except ValueError:
            return None

    def _draw_awards(self, surface: pygame.Surface) -> None:
        x = 620
        y = 96
        heading = self.font.render(_("Awards"), True, config.ACCENT)
        surface.blit(heading, (x, y))
        pygame.draw.line(
            surface, config.GREY, (x, y + 20), (surface.get_width() - 40, y + 20), 1
        )

        awards = self.summary.awards
        if not awards:
            text = self.small_font.render(_("Nobody distinguished themselves."), True, config.GREY)
            surface.blit(text, (x, y + 30))
            return

        for row, result in enumerate(awards):
            top = y + 30 + row * 36
            color = self._player_color(result.player_index)
            title = self.award_font.render(_(result.award.title), True, color)
            surface.blit(title, (x, top))

            winner = _(self.summary.player_names[result.player_index])
            # The unit suffix is part of the translatable format string.
            value = _(result.award.fmt).format(result.value)
            detail = self.small_font.render(
                f"{winner} - {_(result.award.description)}: {value}",
                True,
                config.GREY,
            )
            surface.blit(detail, (x, top + 18))
