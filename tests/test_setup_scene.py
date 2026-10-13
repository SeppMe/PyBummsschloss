"""Tests for the pre-match menu scene: navigation, editing and starting."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from bummsschloss import config  # noqa: E402
from bummsschloss.app import App  # noqa: E402
from bummsschloss.matchsetup import MatchSetup  # noqa: E402
from bummsschloss.scenes.match import MatchScene  # noqa: E402
from bummsschloss.scenes.setup import SetupScene  # noqa: E402


@pytest.fixture
def scene():
    app = App(headless=True)
    menu = SetupScene(app, MatchSetup.default(2))
    app.push_scene(menu)
    app.running = True
    yield menu
    pygame.quit()


def press(scene: SetupScene, key: int, unicode: str = "", mod: int = 0) -> None:
    scene.handle_event(
        pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode, mod=mod)
    )


def select_kind(scene: SetupScene, kind: str, seat: int = -1) -> None:
    for index, row in enumerate(scene.rows()):
        if row.kind == kind and (seat < 0 or row.seat == seat):
            scene.selected = index
            return
    raise AssertionError(f"no {kind} row")


# -- navigation --------------------------------------------------------------


def test_the_row_list_follows_the_player_count(scene):
    assert sum(1 for row in scene.rows() if row.kind == "seat") == 2
    scene.setup.set_player_count(4)
    assert sum(1 for row in scene.rows() if row.kind == "seat") == 4


def test_selection_wraps_around(scene):
    scene.selected = 0
    press(scene, pygame.K_UP)
    assert scene.selected == len(scene.rows()) - 1
    press(scene, pygame.K_DOWN)
    assert scene.selected == 0


def test_the_selection_stays_valid_when_seats_disappear(scene):
    scene.setup.set_player_count(4)
    scene.selected = len(scene.rows()) - 1
    select_kind(scene, "count")
    press(scene, pygame.K_LEFT)
    press(scene, pygame.K_LEFT)
    assert scene.setup.player_count == config.MIN_PLAYERS
    assert scene.current_row in scene.rows()


# -- editing -----------------------------------------------------------------


def test_arrows_change_the_player_count(scene):
    select_kind(scene, "count")
    press(scene, pygame.K_RIGHT)
    assert scene.setup.player_count == 3
    press(scene, pygame.K_LEFT)
    assert scene.setup.player_count == 2


def test_typing_renames_the_selected_seat(scene):
    select_kind(scene, "seat", 0)
    scene.setup.rename(0, "")
    for letter in "Jörg":
        press(scene, ord(letter[0]), unicode=letter)
    assert scene.setup.players[0].name == "Jörg"

    press(scene, pygame.K_BACKSPACE)
    assert scene.setup.players[0].name == "Jör"


def test_typing_replaces_a_default_name_instead_of_appending(scene):
    select_kind(scene, "seat", 1)
    assert scene.setup.is_default_name(1)
    press(scene, ord("Z"), unicode="Z")
    assert scene.setup.players[1].name == "Z"


def test_backspace_clears_a_default_name_in_one_go(scene):
    select_kind(scene, "seat", 1)
    press(scene, pygame.K_BACKSPACE)
    assert scene.setup.players[1].name == ""


def test_arrows_on_a_seat_row_change_the_colour_not_the_name(scene):
    select_kind(scene, "seat", 1)
    before = scene.setup.players[1].name
    colour = scene.setup.players[1].color_index
    press(scene, pygame.K_RIGHT)
    assert scene.setup.players[1].name == before
    assert scene.setup.players[1].color_index != colour


def test_control_keys_are_not_typed_into_the_name(scene):
    select_kind(scene, "seat", 0)
    before = scene.setup.players[0].name
    press(scene, pygame.K_F1, unicode="")
    press(scene, pygame.K_TAB, unicode="\t")
    assert scene.setup.players[0].name == before


def test_economy_rows_change_their_values(scene):
    select_kind(scene, "money")
    before = scene.setup.starting_money
    press(scene, pygame.K_RIGHT)
    assert scene.setup.starting_money != before

    select_kind(scene, "model")
    model = scene.setup.income_model
    press(scene, pygame.K_RIGHT)
    assert scene.setup.income_model is not model


# -- starting ----------------------------------------------------------------


def test_enter_starts_a_match_with_the_chosen_setup(scene):
    scene.setup.set_player_count(3)
    scene.setup.rename(0, "Ada")
    press(scene, pygame.K_RETURN)

    current = scene.app.scene
    assert isinstance(current, MatchScene)
    assert len(current.match.players) == 3
    assert current.match.players[0].name == "Ada"


def test_clicking_the_start_row_starts_the_match(scene):
    for index, row in enumerate(scene.rows()):
        if row.kind == "start":
            centre = scene._row_rect(index).center
            break
    scene.app.mouse_pos = centre
    scene.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=centre))
    assert isinstance(scene.app.scene, MatchScene)


def test_the_menu_draws_every_player_count(scene):
    surface = pygame.Surface(config.LOGICAL_SIZE)
    for count in range(config.MIN_PLAYERS, config.MAX_PLAYERS + 1):
        scene.setup.set_player_count(count)
        scene.update(0.5)
        scene.draw(surface)
