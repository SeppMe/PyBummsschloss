"""The match screen: everything the players see and touch during a game.

This module is the only place that knows about pygame; all rules live in
:mod:`bummsschloss.match`.
"""

from __future__ import annotations

import math

import pygame

from bummsschloss import config
from bummsschloss.i18n import gettext as _
from bummsschloss.match import Match, Phase
from bummsschloss.resources import load_font
from bummsschloss.scenes.base import Scene
from bummsschloss.weapons import ARSENAL

HUD_HEIGHT = 92

#: Width of one player card in the HUD, and the margin to the screen edge.
PANEL_WIDTH = 158
PANEL_MARGIN = 16

#: Layout of the weapon chips along the bottom of the screen.
CHIP_HEIGHT = 20
CHIP_PADDING = 22


def weapon_stat_line(weapon) -> str:
    """The numbers behind a weapon, in one compact line."""
    reach = _("everyone") if weapon.hits_everything else f"{weapon.blast_radius:.0f}"
    return (
        f"{_('damage')} {weapon.damage:.0f}   {_('reach')} {reach}   "
        f"{_('wind')} {weapon.wdabhkt:.0%}   {_('gravity')} {weapon.gravity_scale:.0%}"
    )


class MatchScene(Scene):
    """Draws the match and feeds hotseat input into the rules engine."""

    def __init__(self, app, match: Match | None = None) -> None:
        super().__init__(app)
        self.match = match or Match()

    def on_enter(self) -> None:
        self.font = load_font(15)
        self.small_font = load_font(13)
        self.big_font = load_font(30)
        self._terrain_cache: pygame.Surface | None = None
        self._terrain_version = -1
        self.show_help = False
        self.show_arsenal = False
        self._sky = self._build_sky()

    # -- input --------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        match_ = self.match

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_q):
                self.app.quit()
            elif event.key == pygame.K_h:
                self.show_help = not self.show_help
            elif event.key == pygame.K_w:
                self.show_arsenal = not self.show_arsenal
            elif event.key == pygame.K_n:
                match_.reset(seed=None)
            elif event.key == pygame.K_m:
                self._back_to_menu()
            elif pygame.K_1 <= event.key <= pygame.K_9:
                match_.select_weapon(event.key - pygame.K_1)
            elif event.key == pygame.K_TAB:
                match_.cycle_weapon(-1 if event.mod & pygame.KMOD_SHIFT else 1)
            elif event.key == pygame.K_LEFT:
                match_.adjust_angle(-config.ANGLE_STEP)
            elif event.key == pygame.K_RIGHT:
                match_.adjust_angle(config.ANGLE_STEP)
            elif event.key == pygame.K_UP:
                match_.adjust_power(config.POWER_STEP)
            elif event.key == pygame.K_DOWN:
                match_.adjust_power(-config.POWER_STEP)
            elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                match_.fire()
        elif event.type == pygame.MOUSEMOTION:
            if match_.phase is Phase.AIM:
                match_.aim_at(*self.app.mouse_pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if match_.phase is Phase.AIM:
                match_.aim_at(*self.app.mouse_pos)
                match_.fire()
        elif event.type == pygame.MOUSEWHEEL:
            match_.adjust_power(event.y * config.POWER_STEP)

    # -- simulation ---------------------------------------------------------

    def update(self, dt: float) -> None:
        self.match.update(dt)
        if self.match.phase is Phase.GAME_OVER and self.match.summary is not None:
            from bummsschloss.scenes.summary import SummaryScene

            self.app.replace_scene(SummaryScene(self.app, self.match))

    def _back_to_menu(self) -> None:
        from bummsschloss.scenes.setup import SetupScene

        self.app.replace_scene(SetupScene(self.app, self.match.setup))

    # -- drawing ------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self._sky, (0, 0))
        surface.blit(self._terrain_surface(), (0, 0))
        for castle in self.match.castles:
            self._draw_castle(surface, castle)
        if self.match.phase is Phase.AIM:
            self._draw_aim(surface)
        self._draw_projectiles(surface)
        self._draw_explosions(surface)
        self._draw_hud(surface)
        if self.show_arsenal:
            self._draw_arsenal(surface)
        if self.show_help:
            self._draw_help(surface)

    def _build_sky(self) -> pygame.Surface:
        width, height = config.LOGICAL_SIZE
        sky = pygame.Surface((width, height)).convert()
        bands = 32
        for i in range(bands):
            t = i / (bands - 1)
            color = tuple(
                int(config.SKY[c] + (config.SKY_LOW[c] - config.SKY[c]) * t) for c in range(3)
            )
            pygame.draw.rect(sky, color, (0, i * height // bands, width, height // bands + 1))
        return sky

    def _terrain_surface(self) -> pygame.Surface:
        """Redraw the landscape only when it has actually changed."""
        terrain = self.match.terrain
        if self._terrain_cache is not None and self._terrain_version == terrain.version:
            return self._terrain_cache

        surface = pygame.Surface(config.LOGICAL_SIZE, pygame.SRCALPHA)
        heights = terrain.heights()
        for x, h in enumerate(heights):
            top = int(h)
            if top >= terrain.height:
                continue
            pygame.draw.line(surface, config.GROUND_DARK, (x, top), (x, terrain.height))
            pygame.draw.line(surface, config.GROUND, (x, top), (x, min(top + 5, terrain.height)))
        self._terrain_cache = surface
        self._terrain_version = terrain.version
        return surface

    def _draw_castle(self, surface: pygame.Surface, castle) -> None:
        color = self.match.players[castle.owner].color
        left, top = int(castle.left), int(castle.top_y)
        width, height = int(castle.width), int(castle.height)

        if not castle.alive:
            rubble = pygame.Rect(left, int(castle.bottom_y) - 12, width, 12)
            pygame.draw.rect(surface, config.GREY, rubble)
            return

        body = pygame.Rect(left, top + 16, width, height - 16)
        pygame.draw.rect(surface, config.STONE, body)
        pygame.draw.rect(surface, config.GREY, body, 2)

        # Battlements along the top edge.
        for i in range(0, width, 16):
            pygame.draw.rect(surface, config.STONE, (left + i, top + 6, 10, 12))
            pygame.draw.rect(surface, config.GREY, (left + i, top + 6, 10, 12), 1)

        # Central tower with the owner's banner.
        tower = pygame.Rect(0, 0, 22, 30)
        tower.midbottom = (int(castle.centre_x), top + 18)
        pygame.draw.rect(surface, config.STONE, tower)
        pygame.draw.rect(surface, config.GREY, tower, 2)
        pole_x, pole_y = int(castle.centre_x), tower.top - 14
        pygame.draw.line(surface, config.GREY, (pole_x, tower.top), (pole_x, pole_y), 2)
        pygame.draw.polygon(
            surface, color, [(pole_x, pole_y), (pole_x + 18, pole_y + 5), (pole_x, pole_y + 10)]
        )

        self._draw_health_bar(surface, castle, color)

    def _draw_health_bar(self, surface: pygame.Surface, castle, color) -> None:
        bar = pygame.Rect(0, 0, int(castle.width), 5)
        bar.midbottom = (int(castle.centre_x), int(castle.top_y) - 34)
        if bar.top < HUD_HEIGHT + 4:
            # A castle on a high hill would otherwise hang its bar behind the
            # HUD, where the player's panel already shows the same number.
            return
        pygame.draw.rect(surface, config.BLACK, bar)
        fill = bar.inflate(-2, -2)
        fill.width = max(0, int(fill.width * castle.hp / castle.max_hp))
        pygame.draw.rect(surface, color, fill)
        pygame.draw.rect(surface, config.GREY, bar, 1)

    def _draw_aim(self, surface: pygame.Surface) -> None:
        match_ = self.match
        player = match_.player
        muzzle_x, muzzle_y = match_.castle.muzzle
        angle = math.radians(player.angle)
        color = player.color

        # The barrel itself.
        tip = (muzzle_x + math.cos(angle) * 34, muzzle_y + math.sin(angle) * 34)
        pygame.draw.line(surface, config.GREY, (muzzle_x, muzzle_y), tip, 6)
        pygame.draw.circle(surface, config.STONE, (int(muzzle_x), int(muzzle_y)), 7)

        # A short sighting guide - direction and power only, never the solution.
        length = 30 + 90 * player.power
        for i in range(1, 9):
            t = i / 8
            px = muzzle_x + math.cos(angle) * (34 + length * t)
            py = muzzle_y + math.sin(angle) * (34 + length * t)
            pygame.draw.circle(surface, color, (int(px) % surface.get_width(), int(py)), 2)

    def _draw_projectiles(self, surface: pygame.Surface) -> None:
        width = surface.get_width()
        for projectile in self.match.projectiles:
            color = self.match.players[projectile.owner].color
            for i, (tx, ty) in enumerate(projectile.trail):
                if ty < 0:
                    continue
                fade = (i + 1) / len(projectile.trail)
                tint = tuple(int(c * (0.25 + 0.6 * fade)) for c in color)
                pygame.draw.circle(surface, tint, (int(tx) % width, int(ty)), 1)

            x = int(projectile.x) % width
            if projectile.y < 0:
                self._draw_offscreen_marker(surface, x, color)
            else:
                pygame.draw.circle(surface, config.WHITE, (x, int(projectile.y)), 4)
                pygame.draw.circle(surface, color, (x, int(projectile.y)), 3)

    def _draw_offscreen_marker(self, surface: pygame.Surface, x: int, color) -> None:
        """Show where a shot that has flown above the screen currently is."""
        y = HUD_HEIGHT + 6
        pygame.draw.polygon(surface, color, [(x, y), (x - 6, y + 10), (x + 6, y + 10)])

    def _draw_explosions(self, surface: pygame.Surface) -> None:
        width = surface.get_width()
        for explosion in self.match.explosions:
            t = explosion.progress
            radius = int(explosion.radius * (0.4 + 0.8 * t))
            shade = int(255 * (1.0 - t))
            color = (255, max(120, shade), max(40, shade // 3))
            x = int(explosion.x) % width
            pygame.draw.circle(surface, color, (x, int(explosion.y)), radius, 3)
            pygame.draw.circle(surface, config.ACCENT, (x, int(explosion.y)), max(1, radius // 3))

    # -- HUD ----------------------------------------------------------------

    def _draw_hud(self, surface: pygame.Surface) -> None:
        width = surface.get_width()
        panel = pygame.Surface((width, HUD_HEIGHT), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 160))
        surface.blit(panel, (0, 0))
        pygame.draw.line(surface, config.GREY, (0, HUD_HEIGHT), (width, HUD_HEIGHT), 1)

        match_ = self.match
        for player in match_.players:
            self._draw_player_panel(surface, player, self._panel_x(player.index))
        self._draw_wind(surface)
        self._draw_weapon_bar(surface)

        if match_.last_event:
            text = self.font.render(_(match_.last_event), True, config.ACCENT)
            surface.blit(text, (width // 2 - text.get_width() // 2, HUD_HEIGHT + 8))

        hint = self.small_font.render(_("H for help, W for the arsenal"), True, config.GREY)
        surface.blit(hint, (width - hint.get_width() - 8, HUD_HEIGHT - 16))

    def _panel_x(self, seat: int) -> int:
        """Place the seats in two blocks, leaving the middle free for the wind."""
        total = len(self.match.players)
        left_count = (total + 1) // 2
        if seat < left_count:
            return PANEL_MARGIN + seat * PANEL_WIDTH
        right_slot = seat - left_count
        right_count = total - left_count
        block_start = config.LOGICAL_SIZE[0] - PANEL_MARGIN - right_count * PANEL_WIDTH
        return block_start + right_slot * PANEL_WIDTH

    def _draw_player_panel(self, surface: pygame.Surface, player, x: int) -> None:
        castle = self.match.castle_of(player.index)
        active = player.index == self.match.current_player and castle.alive
        color = player.color

        if active:
            frame = pygame.Rect(x - 6, 4, PANEL_WIDTH - 8, HUD_HEIGHT - 12)
            pygame.draw.rect(surface, color, frame, 1)

        name = _(player.name)
        if not castle.alive:
            name = f"{name} - {_('defeated')}"
        name_color = color if castle.alive else config.GREY
        surface.blit(self.font.render(name, True, name_color), (x, 8))

        self._draw_hud_health(surface, x, 28, castle, color)

        money = self.small_font.render(f"{player.money}", True, config.ACCENT)
        label = self.small_font.render(_("money"), True, config.GREY)
        surface.blit(label, (x, 44))
        surface.blit(money, (x + label.get_width() + 6, 44))

        stats = player.stats
        detail = self.small_font.render(
            f"{_('damage')} {stats.damage_dealt:.0f}   {_('shots')} {stats.shots_fired}",
            True,
            config.GREY,
        )
        surface.blit(detail, (x, 62))

    def _draw_hud_health(
        self, surface: pygame.Surface, x: int, y: int, castle, color
    ) -> None:
        bar = pygame.Rect(x, y + 2, 84, 9)
        pygame.draw.rect(surface, config.BLACK, bar)
        if castle.alive:
            fill = bar.inflate(-2, -2)
            fill.width = max(0, int(fill.width * castle.hp / castle.max_hp))
            pygame.draw.rect(surface, color, fill)
        pygame.draw.rect(surface, config.GREY, bar, 1)
        value = self.small_font.render(f"{max(0.0, castle.hp):.0f}", True, config.WHITE)
        surface.blit(value, (x + bar.width + 8, y))

    def _draw_wind(self, surface: pygame.Surface) -> None:
        centre_x = surface.get_width() // 2
        wind = self.match.wind
        label = self.font.render(_("wind"), True, config.WHITE)
        surface.blit(label, (centre_x - label.get_width() // 2, 8))

        gauge = pygame.Rect(centre_x - 90, 30, 180, 10)
        pygame.draw.rect(surface, config.GREY, gauge, 1)
        pygame.draw.line(surface, config.GREY, (centre_x, 28), (centre_x, 42), 1)

        strength = max(-1.0, min(1.0, wind / config.WIND_MAX))
        bar_width = int(abs(strength) * (gauge.width / 2 - 2))
        if bar_width:
            bar = pygame.Rect(0, gauge.y + 2, bar_width, gauge.height - 4)
            bar.left = centre_x + 1 if strength > 0 else centre_x - 1 - bar_width
            pygame.draw.rect(surface, config.ACCENT, bar)

        arrow = "<<<" if wind < 0 else ">>>"
        text = self.small_font.render(f"{arrow} {abs(wind):.0f}", True, config.WHITE)
        surface.blit(text, (centre_x - text.get_width() // 2, 44))

        turn = self.small_font.render(
            f"{_('turn')} {self.match.turn_number}", True, config.GREY
        )
        surface.blit(turn, (centre_x - turn.get_width() // 2, 62))

    def _draw_weapon_bar(self, surface: pygame.Surface) -> None:
        """The arsenal along the bottom, plus a readout of the chosen weapon.

        The chips wrap onto as many rows as the arsenal needs, so weapons can
        be added without the bar running off the screen.
        """
        player = self.match.player
        width = surface.get_width()
        rows = self._weapon_chip_rows(width)

        panel_height = 54 + len(rows) * CHIP_HEIGHT
        panel_top = surface.get_height() - panel_height
        panel = pygame.Surface((width, panel_height), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 170))
        surface.blit(panel, (0, panel_top))
        pygame.draw.line(surface, config.GREY, (0, panel_top), (width, panel_top), 1)

        self._draw_aim_readout(surface, panel_top + 6)
        self._draw_weapon_info(surface, panel_top + 28)

        y = panel_top + 52
        for row in rows:
            x = PANEL_MARGIN
            for index, label in row:
                self._draw_weapon_chip(surface, index, label, x, y, player)
                x += self.small_font.size(label)[0] + CHIP_PADDING
            y += CHIP_HEIGHT

    def _weapon_chip_rows(self, width: int) -> list[list[tuple[int, str]]]:
        """Lay the weapon labels out into rows that fit the screen."""
        rows: list[list[tuple[int, str]]] = [[]]
        x = PANEL_MARGIN
        for index, weapon in enumerate(ARSENAL):
            label = f"{index + 1} {_(weapon.name)} {weapon.cost}"
            chip_width = self.small_font.size(label)[0] + CHIP_PADDING
            if rows[-1] and x + chip_width > width - PANEL_MARGIN:
                rows.append([])
                x = PANEL_MARGIN
            rows[-1].append((index, label))
            x += chip_width
        return rows

    def _draw_weapon_chip(
        self, surface: pygame.Surface, index: int, label: str, x: int, y: int, player
    ) -> None:
        weapon = ARSENAL[index]
        selected = index == player.weapon_index
        if selected:
            color = config.ACCENT
        elif player.can_afford(weapon):
            color = config.WHITE
        else:
            color = config.GREY
        text = self.small_font.render(label, True, color)
        if selected:
            box = pygame.Rect(x - 5, y - 3, text.get_width() + 10, text.get_height() + 6)
            pygame.draw.rect(surface, config.ACCENT, box, 1)
        surface.blit(text, (x, y))

    def _draw_aim_readout(self, surface: pygame.Surface, y: int) -> None:
        player = self.match.player
        readout = self.font.render(
            f"{_('angle')} {-player.angle:5.1f}°   {_('power')} {player.power * 100:3.0f}%",
            True,
            config.WHITE,
        )
        surface.blit(readout, (PANEL_MARGIN, y))

        if not player.can_afford(player.weapon):
            warning = self.font.render(_("Not enough money for this weapon."), True, config.RED)
            surface.blit(warning, (PANEL_MARGIN + readout.get_width() + 30, y))

    def _draw_weapon_info(self, surface: pygame.Surface, y: int) -> None:
        """Tell the player what the weapon in their hands actually does."""
        weapon = self.match.player.weapon
        name = self.font.render(f"{_(weapon.name)}:", True, config.ACCENT)
        surface.blit(name, (PANEL_MARGIN, y - 2))

        description = self.small_font.render(_(weapon.description), True, config.WHITE)
        surface.blit(description, (PANEL_MARGIN + name.get_width() + 8, y))

        stats = self.small_font.render(weapon_stat_line(weapon), True, config.GREY)
        surface.blit(stats, (surface.get_width() - stats.get_width() - PANEL_MARGIN, y))

    def _draw_arsenal(self, surface: pygame.Surface) -> None:
        """A full table of the arsenal, so weapons can be compared side by side."""
        player = self.match.player
        box = pygame.Rect(0, 0, 840, 72 + len(ARSENAL) * 30)
        box.center = (surface.get_width() // 2, surface.get_height() // 2)

        backdrop = pygame.Surface(box.size, pygame.SRCALPHA)
        backdrop.fill((0, 0, 0, 225))
        surface.blit(backdrop, box.topleft)
        pygame.draw.rect(surface, config.GREY, box, 1)

        heading = self.font.render(_("Arsenal"), True, config.ACCENT)
        surface.blit(heading, (box.left + 20, box.top + 14))
        pygame.draw.line(
            surface,
            config.GREY,
            (box.left + 16, box.top + 38),
            (box.right - 16, box.top + 38),
            1,
        )

        for index, weapon in enumerate(ARSENAL):
            top = box.top + 48 + index * 30
            selected = index == player.weapon_index
            if selected:
                color = config.ACCENT
            elif player.can_afford(weapon):
                color = config.WHITE
            else:
                color = config.GREY

            title = self.font.render(f"{index + 1}  {_(weapon.name)}", True, color)
            surface.blit(title, (box.left + 20, top))

            cost = self.small_font.render(f"{weapon.cost}", True, color)
            surface.blit(cost, (box.left + 232 - cost.get_width(), top + 2))

            stats = self.small_font.render(weapon_stat_line(weapon), True, config.GREY)
            surface.blit(stats, (box.right - stats.get_width() - 20, top + 2))

            description = self.small_font.render(
                _(weapon.description), True, config.GREY if not selected else config.WHITE
            )
            surface.blit(description, (box.left + 252, top + 2))

        hint = self.small_font.render(_("W to close"), True, config.GREY)
        surface.blit(hint, (box.right - hint.get_width() - 20, box.bottom - 22))

    def _draw_help(self, surface: pygame.Surface) -> None:
        entries = [
            (_("mouse"), _("aim")),
            (_("click/space"), _("fire")),
            (_("left/right"), _("fine-tune angle")),
            (_("up/down, wheel"), _("power")),
            ("1-9, Tab", _("choose weapon")),
            ("W", _("show the arsenal")),
            ("N", _("new landscape")),
            ("M", _("back to the menu")),
            ("H", _("hide this help")),
            ("F11", _("fullscreen")),
            ("Esc/Q", _("quit")),
        ]
        box_width, box_height = 330, len(entries) * 22 + 28
        box = pygame.Rect(0, 0, box_width, box_height)
        box.center = (surface.get_width() // 2, surface.get_height() // 2)

        backdrop = pygame.Surface(box.size, pygame.SRCALPHA)
        backdrop.fill((0, 0, 0, 210))
        surface.blit(backdrop, box.topleft)
        pygame.draw.rect(surface, config.GREY, box, 1)

        split = box.left + 130
        for i, (key, description) in enumerate(entries):
            y = box.top + 16 + i * 22
            key_text = self.font.render(key, True, config.ACCENT)
            desc_text = self.font.render(description, True, config.WHITE)
            surface.blit(key_text, (split - 12 - key_text.get_width(), y))
            surface.blit(desc_text, (split, y))
