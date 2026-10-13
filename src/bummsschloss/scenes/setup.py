"""The pre-match menu: seats, names, colours and the rules of the economy.

The screen edits a single :class:`~bummsschloss.matchsetup.MatchSetup` and
hands it to the rules engine when the players are happy. Keyboard and mouse do
the same things: pick a row, change its value, start the game.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from bummsschloss import config
from bummsschloss.i18n import gettext as _
from bummsschloss.matchsetup import MAX_NAME_LENGTH, MatchSetup
from bummsschloss.net import protocol
from bummsschloss.resources import load_font
from bummsschloss.scenes.base import Scene

ROW_TOP = 124
ROW_HEIGHT = 34
LABEL_RIGHT = 392
ARROW_LEFT_X = 410
ARROW_RIGHT_X = 726
VALUE_LEFT = 436
VALUE_RIGHT = 716


@dataclass(frozen=True)
class Row:
    """One editable line of the menu."""

    kind: str
    #: Which seat a ``"seat"`` row belongs to; ``-1`` for the other kinds.
    seat: int = -1

    @property
    def editable_name(self) -> bool:
        return self.kind in ("seat", "myname")

    @property
    def has_arrows(self) -> bool:
        return self.kind not in ("start", "myname")


class SetupScene(Scene):
    """Lets the players agree on the match before a single shot is fired."""

    def __init__(self, app, setup: MatchSetup | None = None) -> None:
        super().__init__(app)
        self.setup = setup or MatchSetup.default()
        self.selected = 0
        #: Hotseat passes one keyboard around; network play uses a broker.
        self.networked = False
        self.hosting = True
        self.room = protocol.new_room_code()
        #: True while the code is one we made up, so the first keystroke of a
        #: player typing somebody else's code replaces it instead of being
        #: silently dropped on a field that is already full.
        self._room_generated = True

    def on_enter(self) -> None:
        self.font = load_font(16)
        self.small_font = load_font(13)
        self.title_font = load_font(34)
        self.subtitle_font = load_font(18)
        self._caret_timer = 0.0
        # Held keys should repeat while typing names or spinning through values.
        pygame.key.set_repeat(350, 45)

    def on_exit(self) -> None:
        pygame.key.set_repeat()

    # -- rows ---------------------------------------------------------------

    def rows(self) -> list[Row]:
        rows = [Row("mode")]
        if self.networked:
            rows += [Row("role"), Row("room"), Row("myname", 0)]
            if self.hosting:
                # Only the host's economy counts, so a guest is not asked.
                rows += [Row("money"), Row("income"), Row("model")]
        else:
            rows.append(Row("count"))
            rows += [Row("seat", seat) for seat in range(self.setup.player_count)]
            rows += [Row("money"), Row("income"), Row("model")]
        rows.append(Row("start"))
        return rows

    @property
    def current_row(self) -> Row:
        rows = self.rows()
        self.selected = max(0, min(len(rows) - 1, self.selected))
        return rows[self.selected]

    def _move_selection(self, step: int) -> None:
        count = len(self.rows())
        self.selected = (self.selected + step) % count

    # -- input --------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self._handle_key(event)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(self.app.mouse_pos)
        elif event.type == pygame.MOUSEMOTION:
            hit = self._row_at(self.app.mouse_pos)
            if hit is not None:
                self.selected = hit

    def _handle_key(self, event: pygame.event.Event) -> None:
        row = self.current_row
        if event.key == pygame.K_ESCAPE:
            self.app.quit()
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.start_match()
        elif event.key == pygame.K_UP:
            self._move_selection(-1)
        elif event.key == pygame.K_DOWN:
            self._move_selection(1)
        elif event.key == pygame.K_TAB:
            self._move_selection(-1 if event.mod & pygame.KMOD_SHIFT else 1)
        elif event.key == pygame.K_LEFT:
            self._adjust(row, -1)
        elif event.key == pygame.K_RIGHT:
            self._adjust(row, 1)
        elif event.key == pygame.K_BACKSPACE and row.kind == "room":
            # A code we made up goes in one go; one the player typed, letter
            # by letter.
            self.room = "" if self._room_generated else self.room[:-1]
            self._room_generated = False
        elif event.key == pygame.K_BACKSPACE and row.editable_name:
            # Rubbing out a default name clears the whole field at once.
            if self.setup.is_default_name(row.seat):
                self.setup.rename(row.seat, "")
            else:
                self.setup.rename(row.seat, self.setup.players[row.seat].name[:-1])
        elif row.kind == "room" and self._is_typable(event.unicode):
            base = "" if self._room_generated else self.room
            self._room_generated = False
            self.room = protocol.clean_room_code(base + event.unicode)
        elif row.editable_name and self._is_typable(event.unicode):
            # The first keystroke replaces the default name rather than
            # appending to it, so nobody has to delete "Player 3" by hand.
            base = "" if self.setup.is_default_name(row.seat) else self.setup.players[row.seat].name
            self.setup.rename(row.seat, base + event.unicode)

    @staticmethod
    def _is_typable(text: str) -> bool:
        """Accept ordinary printable characters, including umlauts."""
        return bool(text) and text.isprintable() and text != "\t"

    def _adjust(self, row: Row, step: int) -> None:
        if row.kind == "mode":
            self.networked = not self.networked
            self.selected = min(self.selected, len(self.rows()) - 1)
        elif row.kind == "role":
            self.hosting = not self.hosting
            # A guest needs an empty field to type the host's code into; a
            # host needs a code to read out.
            self.room = protocol.new_room_code() if self.hosting else ""
            self._room_generated = self.hosting
            self.selected = min(self.selected, len(self.rows()) - 1)
        elif row.kind == "room":
            # Only the host has anything to cycle through - a guest must type
            # the one code that gets them to their friends.
            if self.hosting:
                self.room = protocol.new_room_code()
                self._room_generated = True
        elif row.kind == "count":
            self.setup.set_player_count(self.setup.player_count + step)
            self.selected = min(self.selected, len(self.rows()) - 1)
        elif row.kind == "seat":
            self.setup.cycle_color(row.seat, step)
        elif row.kind == "money":
            self.setup.cycle_starting_money(step)
        elif row.kind == "income":
            self.setup.cycle_turn_income(step)
        elif row.kind == "model":
            self.setup.cycle_income_model(step)

    def _handle_click(self, pos: tuple[int, int]) -> None:
        hit = self._row_at(pos)
        if hit is None:
            return
        self.selected = hit
        row = self.rows()[hit]
        if row.kind == "start":
            self.start_match()
        elif self._takes_arrows(row):
            if self._arrow_rect(hit, -1).collidepoint(pos):
                self._adjust(row, -1)
            elif self._arrow_rect(hit, 1).collidepoint(pos):
                self._adjust(row, 1)

    def _row_at(self, pos: tuple[int, int]) -> int | None:
        for index in range(len(self.rows())):
            if self._row_rect(index).collidepoint(pos):
                return index
        return None

    def start_match(self) -> None:
        if self.networked:
            self.start_network_game()
            return
        from bummsschloss.match import Match
        from bummsschloss.scenes.match import MatchScene

        match_ = Match(setup=self.setup, seed=self.setup.seed)
        self.app.replace_scene(MatchScene(self.app, match_))

    def start_network_game(self) -> None:
        """Open the room on the broker and move to the lobby."""
        from bummsschloss.net.session import NetSession
        from bummsschloss.net.transport import MqttTransport
        from bummsschloss.scenes.lobby import LobbyScene

        room = protocol.clean_room_code(self.room)
        if len(room) < protocol.ROOM_CODE_LENGTH:
            self.room = room
            return  # an incomplete code would put the player in a room of one
        self.room = room

        session = NetSession(
            MqttTransport(room),
            name=self.setup.display_name(0),
            is_host=self.hosting,
            room=room,
            setup=self.setup,
        )
        self.app.replace_scene(LobbyScene(self.app, session, self.setup))

    # -- geometry -----------------------------------------------------------

    def _row_rect(self, index: int) -> pygame.Rect:
        return pygame.Rect(120, ROW_TOP + index * ROW_HEIGHT - 4, 720, ROW_HEIGHT - 4)

    def _arrow_rect(self, index: int, direction: int) -> pygame.Rect:
        x = ARROW_LEFT_X if direction < 0 else ARROW_RIGHT_X
        return pygame.Rect(x - 6, ROW_TOP + index * ROW_HEIGHT - 4, 30, ROW_HEIGHT - 6)

    # -- simulation ---------------------------------------------------------

    def update(self, dt: float) -> None:
        self._caret_timer += dt

    # -- drawing ------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(config.SKY)
        self._draw_header(surface)

        for index, row in enumerate(self.rows()):
            self._draw_row(surface, index, row)

        self._draw_footer(surface)

    def _draw_header(self, surface: pygame.Surface) -> None:
        title = self.title_font.render(config.GAME_TITLE, True, config.ACCENT)
        surface.blit(title, (surface.get_width() // 2 - title.get_width() // 2, 28))
        subtitle = self.subtitle_font.render(_("Set up the match"), True, config.WHITE)
        surface.blit(subtitle, (surface.get_width() // 2 - subtitle.get_width() // 2, 72))

    def _draw_row(self, surface: pygame.Surface, index: int, row: Row) -> None:
        selected = index == self.selected
        y = ROW_TOP + index * ROW_HEIGHT
        if selected:
            highlight = self._row_rect(index)
            backdrop = pygame.Surface(highlight.size, pygame.SRCALPHA)
            backdrop.fill((255, 255, 255, 22))
            surface.blit(backdrop, highlight.topleft)

        if row.kind == "start":
            self._draw_start(surface, y, selected)
            return

        label = self.font.render(self._label_for(row), True, config.WHITE)
        surface.blit(label, (LABEL_RIGHT - label.get_width(), y))

        if row.kind == "seat":
            self._draw_seat_value(surface, row.seat, y, selected)
        elif row.kind == "myname":
            self._draw_seat_value(surface, row.seat, y, selected, swatch=False)
        elif row.kind == "room":
            self._draw_room_value(surface, y, selected)
        else:
            value = self.font.render(self._value_for(row), True, config.ACCENT)
            centre = (VALUE_LEFT + VALUE_RIGHT) // 2
            surface.blit(value, (centre - value.get_width() // 2, y))

        if self._takes_arrows(row) and selected:
            for direction, glyph in ((-1, "<"), (1, ">")):
                arrow = self.font.render(glyph, True, config.ACCENT)
                surface.blit(arrow, self._arrow_rect(index, direction).topleft)

    def _takes_arrows(self, row: Row) -> bool:
        """Whether this row has anything to step through right now."""
        if row.kind == "room":
            # A guest has to type the host's code; there is nothing to cycle.
            return self.hosting
        return row.has_arrows

    def _draw_room_value(self, surface: pygame.Surface, y: int, selected: bool) -> None:
        """The room code as a typable field, with the empty slots shown."""
        code = self.room
        filled = self.font.render(code, True, config.ACCENT)
        missing = "_" * (protocol.ROOM_CODE_LENGTH - len(code))
        blanks = self.font.render(missing, True, config.GREY)

        centre = (VALUE_LEFT + VALUE_RIGHT) // 2
        left = centre - (filled.get_width() + blanks.get_width()) // 2
        surface.blit(filled, (left, y))
        surface.blit(blanks, (left + filled.get_width(), y))

        if selected and len(code) < protocol.ROOM_CODE_LENGTH:
            if int(self._caret_timer * 2) % 2 == 0:
                caret_x = left + filled.get_width() + 1
                pygame.draw.line(
                    surface, config.WHITE, (caret_x, y + 2), (caret_x, y + 17), 1
                )

    def _label_for(self, row: Row) -> str:
        if row.kind == "mode":
            return _("game type")
        if row.kind == "role":
            return _("role")
        if row.kind == "room":
            return _("room code")
        if row.kind == "myname":
            return _("your name")
        if row.kind == "count":
            return _("players")
        if row.kind == "seat":
            return _("seat {number}").format(number=row.seat + 1)
        if row.kind == "money":
            return _("starting money")
        if row.kind == "income":
            return _("income per turn")
        return _("economy")

    def _value_for(self, row: Row) -> str:
        if row.kind == "mode":
            return _("network") if self.networked else _("hotseat")
        if row.kind == "role":
            return _("host") if self.hosting else _("join")
        if row.kind == "room":
            return self.room or "-----"
        if row.kind == "count":
            return str(self.setup.player_count)
        if row.kind == "money":
            return str(self.setup.starting_money)
        if row.kind == "income":
            return str(self.setup.turn_income)
        return _(self.setup.income_model.label)

    def _draw_seat_value(
        self, surface: pygame.Surface, seat: int, y: int, selected: bool, swatch: bool = True
    ) -> None:
        player = self.setup.players[seat]
        text_left = VALUE_LEFT
        if swatch:
            box = pygame.Rect(VALUE_LEFT, y + 2, 16, 16)
            pygame.draw.rect(surface, player.color, box)
            pygame.draw.rect(surface, config.GREY, box, 1)
            text_left = VALUE_LEFT + 26

        name = player.name
        # Default names are source strings, so they get translated for display.
        label = _(name) if self.setup.is_default_name(seat) else name
        color = player.color if swatch else config.ACCENT
        text = self.font.render(label or _("(unnamed)"), True, color)
        surface.blit(text, (text_left, y))

        if selected:
            # A blinking caret shows that this field takes typing.
            if int(self._caret_timer * 2) % 2 == 0 and len(name) < MAX_NAME_LENGTH:
                caret_x = text_left + 2 + text.get_width()
                pygame.draw.line(
                    surface, config.WHITE, (caret_x, y + 2), (caret_x, y + 17), 1
                )

    def _draw_start(self, surface: pygame.Surface, y: int, selected: bool) -> None:
        color = config.ACCENT if selected else config.WHITE
        text = self.font.render(self._start_label(), True, color)
        box = pygame.Rect(0, 0, text.get_width() + 36, text.get_height() + 10)
        box.midtop = (surface.get_width() // 2, y - 5)
        pygame.draw.rect(surface, color, box, 1)
        surface.blit(text, (box.centerx - text.get_width() // 2, y))

    def _start_label(self) -> str:
        if not self.networked:
            return _("Start the match")
        return _("Open the room") if self.hosting else _("Join the room")

    def _draw_footer(self, surface: pygame.Surface) -> None:
        bottom = surface.get_height()
        explanation = self.small_font.render(self._explanation(), True, config.GREY)
        surface.blit(
            explanation, (surface.get_width() // 2 - explanation.get_width() // 2, bottom - 70)
        )

        hint = self.small_font.render(
            _("arrow keys to choose   -   Enter to start   -   Esc to quit"),
            True,
            config.GREY,
        )
        surface.blit(hint, (surface.get_width() // 2 - hint.get_width() // 2, bottom - 40))

    def _explanation(self) -> str:
        """One line about whatever row is selected right now."""
        row = self.current_row
        if row.kind == "mode":
            if self.networked:
                return _("Everyone plays at their own machine, over the internet.")
            return _("Everybody at one keyboard, passing it around.")
        if row.kind == "role":
            if self.hosting:
                return _("You open the room and start the match.")
            return _("Enter the code your host read out to you.")
        if row.kind == "room":
            if self.hosting:
                return _("Five characters. Arrow keys roll a fresh code.")
            return _("Type the code your host gave you, five characters.")
        if row.kind == "myname":
            return _("type to rename")
        if row.kind == "seat":
            return _("type to rename, arrows for colour")
        if row.kind == "start":
            if self.networked:
                return _("No port forwarding needed - everybody dials out.")
            return _("Everything ready? Then let the cannons speak.")
        return _(self.setup.income_model.description)
