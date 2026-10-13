"""The waiting room of a networked match.

Everybody who has entered the same room code gathers here until the host
starts the game. The scene itself does almost nothing: it polls the
:class:`~bummsschloss.net.session.NetSession` once a frame, shows who has
arrived, and moves on to the match as soon as the session has one.
"""

from __future__ import annotations

import time

import pygame

from bummsschloss import config
from bummsschloss.i18n import gettext as _
from bummsschloss.matchsetup import MatchSetup
from bummsschloss.net.session import NetSession, SessionState
from bummsschloss.resources import load_font
from bummsschloss.scenes.base import Scene

ROW_TOP = 236
ROW_HEIGHT = 30


class LobbyScene(Scene):
    """Shows the room code and the players in it, and waits for the host."""

    def __init__(self, app, session: NetSession, setup: MatchSetup | None = None) -> None:
        super().__init__(app)
        self.session = session
        self.setup = setup

    def on_enter(self) -> None:
        self.font = load_font(16)
        self.small_font = load_font(13)
        self.title_font = load_font(34)
        self.code_font = load_font(46)
        self.subtitle_font = load_font(18)
        self._blink = 0.0

    def on_exit(self) -> None:
        pygame.key.set_repeat()

    # -- input --------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_ESCAPE, pygame.K_m):
            self._leave()
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.session.start_match()

    def _leave(self) -> None:
        from bummsschloss.scenes.setup import SetupScene

        self.session.close()
        self.app.replace_scene(SetupScene(self.app, self.setup))

    # -- simulation ---------------------------------------------------------

    def update(self, dt: float) -> None:
        self._blink += dt
        self.session.poll(time.monotonic())
        if self.session.match is not None:
            from bummsschloss.scenes.match import MatchScene

            self.app.replace_scene(MatchScene(self.app, self.session.match, self.session))

    # -- drawing ------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(config.SKY)
        width = surface.get_width()

        title = self.title_font.render(config.GAME_TITLE, True, config.ACCENT)
        surface.blit(title, (width // 2 - title.get_width() // 2, 28))
        subtitle = self.subtitle_font.render(_("Waiting room"), True, config.WHITE)
        surface.blit(subtitle, (width // 2 - subtitle.get_width() // 2, 72))

        self._draw_room_code(surface, width)
        self._draw_peers(surface, width)
        self._draw_footer(surface, width)

    def _draw_room_code(self, surface: pygame.Surface, width: int) -> None:
        label = self.small_font.render(_("room code"), True, config.GREY)
        surface.blit(label, (width // 2 - label.get_width() // 2, 118))
        code = self.code_font.render(self.session.room or "-----", True, config.WHITE)
        surface.blit(code, (width // 2 - code.get_width() // 2, 138))

        hint = self.small_font.render(
            _("Read this code out to the others."), True, config.GREY
        )
        surface.blit(hint, (width // 2 - hint.get_width() // 2, 196))

    def _draw_peers(self, surface: pygame.Surface, width: int) -> None:
        peers = self.session.peers
        if not peers:
            text = self.font.render(self._status(), True, config.GREY)
            surface.blit(text, (width // 2 - text.get_width() // 2, ROW_TOP))
            return

        for index, peer in enumerate(peers):
            y = ROW_TOP + index * ROW_HEIGHT
            color = config.player_color(index)
            swatch = pygame.Rect(width // 2 - 150, y + 3, 14, 14)
            pygame.draw.rect(surface, color, swatch)
            pygame.draw.rect(surface, config.GREY, swatch, 1)

            name = peer.display_name
            if peer.peer_id == self.session.peer_id:
                name = f"{name}  ({_('you')})"
            text = self.font.render(name, True, config.WHITE)
            surface.blit(text, (width // 2 - 126, y))

            seat = self.small_font.render(
                _("seat {number}").format(number=index + 1), True, config.GREY
            )
            surface.blit(seat, (width // 2 + 96, y + 2))

    def _status(self) -> str:
        session = self.session
        if session.state is SessionState.FAILED:
            return _("No connection: {reason}").format(reason=session.failure or "?")
        if session.state is SessionState.CONNECTING:
            return _("Connecting to the broker...")
        return _("Nobody here yet.")

    def _draw_footer(self, surface: pygame.Surface, width: int) -> None:
        bottom = surface.get_height()
        session = self.session

        if session.state is SessionState.FAILED:
            message = self._status()
            color = config.ACCENT
        elif session.state is SessionState.CONNECTING:
            message = _("Connecting to the broker...")
            color = config.GREY
        elif session.is_host:
            if session.can_start():
                message = _("Enter starts the match")
                color = config.ACCENT if int(self._blink * 2) % 2 == 0 else config.WHITE
            else:
                message = _("At least one more player is needed.")
                color = config.GREY
        else:
            message = _("Waiting for the host to start...")
            color = config.GREY

        text = self.font.render(message, True, color)
        surface.blit(text, (width // 2 - text.get_width() // 2, bottom - 76))

        hint = self.small_font.render(_("Esc to leave the room"), True, config.GREY)
        surface.blit(hint, (width // 2 - hint.get_width() // 2, bottom - 40))
