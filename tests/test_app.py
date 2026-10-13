"""Tests for window handling: resizing, fullscreen and coordinate mapping."""

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


def test_fullscreen_toggle_keeps_a_usable_window(app):
    """SDL may hand back a new surface; the app must adopt it."""
    app.push_scene(MatchScene(app, Match(setup=MatchSetup.default(2), seed=7)))
    app.running = True

    app.toggle_fullscreen()
    assert app.fullscreen
    assert app.window is pygame.display.get_surface()
    app.step(1 / 60)

    app.toggle_fullscreen()
    assert not app.fullscreen
    assert app.window is pygame.display.get_surface()
    assert app.window.get_size() == config.WINDOW_SIZE
    app.step(1 / 60)


def test_resizing_updates_the_window_and_the_mapping(app):
    app.push_scene(MatchScene(app, Match(setup=MatchSetup.default(2), seed=7)))
    app.running = True

    pygame.event.post(pygame.event.Event(pygame.VIDEORESIZE, w=640, h=360, size=(640, 360)))
    app.step(1 / 60)

    assert app.window.get_size() == (640, 360)
    centre = app.to_logical((320, 180))
    assert abs(centre[0] - config.LOGICAL_SIZE[0] // 2) <= 2
    assert abs(centre[1] - config.LOGICAL_SIZE[1] // 2) <= 2


def test_letterboxing_preserves_the_aspect_ratio(app):
    pygame.event.post(pygame.event.Event(pygame.VIDEORESIZE, w=1600, h=400, size=(1600, 400)))
    app.push_scene(MatchScene(app, Match(setup=MatchSetup.default(2), seed=7)))
    app.running = True
    app.step(1 / 60)

    view = app._viewport()
    logical_ratio = config.LOGICAL_SIZE[0] / config.LOGICAL_SIZE[1]
    assert view.width / view.height == pytest.approx(logical_ratio, abs=0.02)
    assert view.width <= 1600 and view.height <= 400

