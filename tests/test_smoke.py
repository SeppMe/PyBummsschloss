"""Headless smoke tests: they must run without a real window or GPU."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from bummsschloss import config  # noqa: E402
from bummsschloss.app import App  # noqa: E402
from bummsschloss.match import Match  # noqa: E402
from bummsschloss.matchsetup import MatchSetup  # noqa: E402
from bummsschloss.scenes.match import MatchScene  # noqa: E402


@pytest.fixture
def app():
    application = App(headless=True)
    yield application
    pygame.quit()


def a_match(app) -> MatchScene:
    """A real match on the stack - the cheapest scene that exercises everything."""
    scene = MatchScene(app, Match(setup=MatchSetup.default(2), seed=7))
    app.push_scene(scene)
    app.running = True
    return scene


def test_app_runs_frames_and_draws(app):
    a_match(app)
    for _step in range(10):
        app.step(1 / 60)
    assert app.running
    assert app.screen.get_size() == config.LOGICAL_SIZE


def test_a_shot_leaves_the_barrel(app):
    scene = a_match(app)
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=""))
    assert scene.match.projectiles, "space should fire the cannon"


def test_logical_coordinate_mapping(app):
    centre = (app.window.get_width() // 2, app.window.get_height() // 2)
    lx, ly = app.to_logical(centre)
    assert abs(lx - config.LOGICAL_SIZE[0] // 2) <= 1
    assert abs(ly - config.LOGICAL_SIZE[1] // 2) <= 1


def test_quit_event_stops_the_loop(app):
    a_match(app)
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    app.step(1 / 60)
    assert not app.running
