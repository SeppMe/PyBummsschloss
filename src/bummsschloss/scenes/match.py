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
        self._sky = self._build_sky()

    # -- input --------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        match_ = self.match

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_q):
                self.app.quit()
            elif event.key == pygame.K_h:
                self.show_help = not self.show_help
            elif event.key == pygame.K_n:
                match_.reset(seed=None)
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
        color = config.PLAYER_COLORS[castle.owner % len(config.PLAYER_COLORS)]
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
        color = config.PLAYER_COLORS[player.index % len(config.PLAYER_COLORS)]

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
            color = config.PLAYER_COLORS[projectile.owner % len(config.PLAYER_COLORS)]
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
            self._draw_player_panel(surface, player)
        self._draw_wind(surface)
        self._draw_weapon_bar(surface)

        if match_.last_event:
            text = self.font.render(_(match_.last_event), True, config.ACCENT)
            surface.blit(text, (width // 2 - text.get_width() // 2, HUD_HEIGHT + 8))

        hint = self.small_font.render(_("H for help"), True, config.GREY)
        surface.blit(hint, (width - hint.get_width() - 8, HUD_HEIGHT - 18))

    def _draw_player_panel(self, surface: pygame.Surface, player) -> None:
        active = player.index == self.match.current_player
        color = config.PLAYER_COLORS[player.index % len(config.PLAYER_COLORS)]
        right_aligned = player.index == 1
        x = surface.get_width() - 18 if right_aligned else 18

        def blit(text: pygame.Surface, y: int) -> None:
            surface.blit(text, (x - text.get_width() if right_aligned else x, y))

        name = f"{_(player.name)}"
        if active:
            name = f"> {name}" if not right_aligned else f"{name} <"
        blit(self.font.render(name, True, color if active else config.GREY), 10)

        castle = self.match.castle_of(player.index)
        blit(
            self.small_font.render(
                f"{_('armour')} {castle.hp:.0f}/{castle.max_hp:.0f}", True, config.WHITE
            ),
            30,
        )
        blit(
            self.small_font.render(f"{_('money')} {player.money}", True, config.ACCENT),
            46,
        )
        stats = player.stats
        blit(
            self.small_font.render(
                f"{_('damage')} {stats.damage_dealt:.0f}   "
                f"{_('shots')} {stats.shots_fired}",
                True,
                config.GREY,
            ),
            62,
        )

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
        player = self.match.player
        y = surface.get_height() - 26
        x = 18
        for index, weapon in enumerate(ARSENAL):
            selected = index == player.weapon_index
            affordable = player.can_afford(weapon)
            if selected:
                color = config.ACCENT
            elif affordable:
                color = config.WHITE
            else:
                color = config.GREY
            label = f"{index + 1} {_(weapon.name)} {weapon.cost}"
            text = self.font.render(label, True, color)
            if selected:
                box = pygame.Rect(x - 5, y - 4, text.get_width() + 10, text.get_height() + 8)
                pygame.draw.rect(surface, config.GREY, box, 1)
            surface.blit(text, (x, y))
            x += text.get_width() + 26

        readout = self.font.render(
            f"{_('angle')} {-player.angle:5.1f}°   {_('power')} {player.power * 100:3.0f}%",
            True,
            config.WHITE,
        )
        surface.blit(readout, (18, y - 26))

        if not player.can_afford(player.weapon):
            warning = self.font.render(_("Not enough money for this weapon."), True, config.RED)
            surface.blit(warning, (18, y - 48))

    def _draw_help(self, surface: pygame.Surface) -> None:
        entries = [
            (_("mouse"), _("aim")),
            (_("click/space"), _("fire")),
            (_("left/right"), _("fine-tune angle")),
            (_("up/down, wheel"), _("power")),
            ("1-6, Tab", _("choose weapon")),
            ("N", _("new landscape")),
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
