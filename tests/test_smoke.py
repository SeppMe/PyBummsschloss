"""Headless smoke tests: they must run without a real window or GPU."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from bummsschloss import config  # noqa: E402
from bummsschloss.app import App  # noqa: E402
from bummsschloss.scenes.demo import GROUND_Y, Ball, DemoScene  # noqa: E402


@pytest.fixture
def app():
    application = App(headless=True)
    yield application
    pygame.quit()


def test_ball_falls_and_settles():
    ball = Ball(x=100.0, y=100.0, vx=0.0, vy=0.0, radius=5, color=config.WHITE)
    for _ in range(2000):
        ball.update(config.FIXED_DT)
        if not ball.alive:
            break
    assert not ball.alive, "ball should come to rest eventually"
    assert ball.y + ball.radius == pytest.approx(GROUND_Y, abs=1.0)


def test_ball_stays_inside_playfield():
    ball = Ball(x=10.0, y=50.0, vx=-900.0, vy=0.0, radius=6, color=config.WHITE)
    for _ in range(600):
        ball.update(config.FIXED_DT)
        assert 0 <= ball.x <= config.LOGICAL_SIZE[0]


def test_app_runs_frames_and_draws(app):
    scene = DemoScene(app)
    app.push_scene(scene)
    app.running = True
    for _ in range(10):
        app.step(1 / 60)
    assert app.running
    assert app.screen.get_size() == config.LOGICAL_SIZE


def test_firing_adds_a_ball(app):
    scene = DemoScene(app)
    app.push_scene(scene)
    before = len(scene.balls)
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
    assert len(scene.balls) == before + 1


def test_logical_coordinate_mapping(app):
    centre = (app.window.get_width() // 2, app.window.get_height() // 2)
    lx, ly = app.to_logical(centre)
    assert abs(lx - config.LOGICAL_SIZE[0] // 2) <= 1
    assert abs(ly - config.LOGICAL_SIZE[1] // 2) <= 1


def test_quit_event_stops_the_loop(app):
    app.push_scene(DemoScene(app))
    app.running = True
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    app.step(1 / 60)
    assert not app.running
