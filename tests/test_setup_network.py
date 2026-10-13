"""Tests for the network side of the menus: the game-type choice and the lobby."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from bummsschloss import config  # noqa: E402
from bummsschloss.app import App  # noqa: E402
from bummsschloss.matchsetup import MatchSetup  # noqa: E402
from bummsschloss.net import protocol  # noqa: E402
from bummsschloss.net.session import NetSession  # noqa: E402
from bummsschloss.net.transport import LoopbackBus  # noqa: E402
from bummsschloss.scenes.lobby import LobbyScene  # noqa: E402
from bummsschloss.scenes.setup import SetupScene  # noqa: E402


@pytest.fixture
def app():
    application = App(headless=True)
    application.running = True
    yield application
    pygame.quit()


def press(scene, key, unicode=""):
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=unicode))


def kinds(scene) -> list[str]:
    return [row.kind for row in scene.rows()]


# -- the game-type choice ----------------------------------------------------


def test_the_menu_starts_in_hotseat(app):
    scene = SetupScene(app)
    app.push_scene(scene)
    assert not scene.networked
    assert kinds(scene)[:2] == ["mode", "count"]


def test_switching_to_network_swaps_the_rows(app):
    scene = SetupScene(app)
    app.push_scene(scene)
    scene._adjust(scene.rows()[0], 1)

    assert scene.networked
    assert kinds(scene) == ["mode", "role", "room", "myname", "money", "income", "model", "start"]


def test_a_guest_is_not_asked_about_the_economy(app):
    scene = SetupScene(app)
    app.push_scene(scene)
    scene.networked = True
    scene.hosting = False
    assert kinds(scene) == ["mode", "role", "room", "myname", "start"]


def test_a_host_gets_a_room_code_to_read_out(app):
    scene = SetupScene(app)
    app.push_scene(scene)
    assert len(scene.room) == protocol.ROOM_CODE_LENGTH


def test_a_guest_types_the_code_they_were_given(app):
    scene = SetupScene(app)
    app.push_scene(scene)
    scene.networked = True
    scene.hosting = False
    scene.room = ""
    scene.selected = kinds(scene).index("room")

    for char in "qw3rt!":  # the "!" is not part of the alphabet and is dropped
        press(scene, ord(char), char)
    assert scene.room == "QW3RT"

    press(scene, pygame.K_BACKSPACE)
    assert scene.room == "QW3R"


def test_an_incomplete_code_does_not_open_a_room(app):
    scene = SetupScene(app)
    app.push_scene(scene)
    scene.networked = True
    scene.hosting = False
    scene.room = "AB"
    scene.start_match()
    assert app.scene is scene, "a half-typed code must not take us anywhere"


def test_the_network_menu_still_draws(app):
    scene = SetupScene(app)
    app.push_scene(scene)
    scene.networked = True
    for index in range(len(scene.rows())):
        scene.selected = index
        scene.update(0.016)
        scene.draw(app.screen)


# -- the waiting room --------------------------------------------------------


@pytest.fixture
def lobby(app):
    bus = LoopbackBus()
    session = NetSession(
        bus.connect("host"),
        name="Host",
        is_host=True,
        room="AB3CD",
        setup=MatchSetup.default(2),
    )
    scene = LobbyScene(app, session, MatchSetup.default(2))
    app.push_scene(scene)
    return scene


def test_the_lobby_shows_the_room_code(lobby):
    lobby.update(0.016)
    lobby.draw(lobby.app.screen)
    assert lobby.session.room == "AB3CD"
    assert [peer.display_name for peer in lobby.session.peers] == ["Host"]


def test_the_lobby_moves_on_once_the_match_begins(lobby):
    from bummsschloss.scenes.match import MatchScene

    bus = lobby.session.transport.bus
    guest = NetSession(bus.connect("guest"), name="Gast", is_host=False)
    for step in range(6):
        guest.poll(step * 0.5)
        lobby.update(0.016)

    assert lobby.session.can_start()
    lobby.session.start_match()
    lobby.update(0.016)

    assert isinstance(lobby.app.scene, MatchScene)
    assert lobby.app.scene.session is lobby.session


def test_leaving_the_lobby_closes_the_room(lobby):
    press(lobby, pygame.K_ESCAPE)
    assert isinstance(lobby.app.scene, SetupScene)
    assert not lobby.session.transport.connected


# -- broker addresses --------------------------------------------------------


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("wss://test.mosquitto.org:8081/mqtt", ("wss", "test.mosquitto.org", 8081, "/mqtt")),
        ("tcp://broker.hivemq.com:1883", ("tcp", "broker.hivemq.com", 1883, "/mqtt")),
        ("broker.hivemq.com", ("tcp", "broker.hivemq.com", 1883, "/mqtt")),
        ("wss://example.org", ("wss", "example.org", 443, "/mqtt")),
        ("http://proxy.local:8080/", ("tcp", "proxy.local", 8080, "/mqtt")),
    ],
)
def test_broker_addresses_are_understood(address, expected):
    assert config.parse_broker(address) == expected
