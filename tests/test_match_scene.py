"""Tests for the match view: what actually ends up on the screen."""

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
def scene():
    app = App(headless=True)
    view = MatchScene(app, Match(setup=MatchSetup.default(2), seed=3))
    app.push_scene(view)
    app.running = True
    yield view
    pygame.quit()


def stone_in(surface: pygame.Surface, columns, rows) -> bool:
    return any(surface.get_at((x, y))[:3] == config.STONE for x in columns for y in rows)


def test_a_castle_on_the_seam_is_drawn_on_both_edges(scene):
    """The world wraps, so half a castle must not simply go missing."""
    castle = scene.match.castles[0]
    castle.centre_x = 4.0
    surface = scene.app.screen
    scene.draw(surface)

    rows = range(int(castle.top_y) + 5, int(castle.top_y + castle.height) - 2)
    assert stone_in(surface, range(0, 20), rows)
    assert stone_in(surface, range(surface.get_width() - 20, surface.get_width()), rows)


def test_the_new_landscape_shortcut_is_gone(scene):
    """N used to reroll the map; it does nothing now."""
    before = scene.match.terrain.heights()
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_n, unicode="n", mod=0))
    assert scene.match.terrain.heights() == before
