"""The scene framework.

A *scene* is one self-contained screen of the game: the title menu, the match
itself, the end-of-round summary, and so on. The :class:`~bummsschloss.app.App`
owns a stack of scenes and drives the top one.

Scenes implement three things:

``handle_event``  react to a single pygame event (input)
``update``        advance the simulation by a *fixed* time step
``draw``          render onto the logical surface

Keeping update and draw apart means the simulation stays deterministic while
rendering can happen at whatever rate the monitor allows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:  # pragma: no cover - typing only
    from bummsschloss.app import App


class Scene:
    """Base class for all scenes. Override what you need."""

    def __init__(self, app: App) -> None:
        self.app = app

    # -- lifecycle ----------------------------------------------------------

    def on_enter(self) -> None:
        """Called when the scene becomes the active one."""

    def on_exit(self) -> None:
        """Called when the scene is removed or covered by another scene."""

    # -- per-frame ----------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        """React to one input event."""

    def update(self, dt: float) -> None:
        """Advance the simulation by exactly ``dt`` seconds."""

    def draw(self, surface: pygame.Surface) -> None:
        """Render the scene onto the logical-resolution ``surface``."""
