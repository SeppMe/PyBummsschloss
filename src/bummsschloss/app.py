"""Window management and the main loop.

The game is rendered at a fixed *logical* resolution (see
:data:`bummsschloss.config.LOGICAL_SIZE`) and then scaled to fit the window. That
keeps all gameplay code in one coordinate system no matter how the user resizes
the window, and gives the picture the chunky look of the old demo games.
"""

from __future__ import annotations

import pygame

from bummsschloss import config, resources
from bummsschloss.scenes.base import Scene


class App:
    """Owns the window, the clock and the stack of scenes."""

    def __init__(self, *, headless: bool = False) -> None:
        self.headless = headless
        self.running = False
        self._scenes: list[Scene] = []

        pygame.init()
        resources.clear_cache()
        self._window_flags = pygame.RESIZABLE | (pygame.HIDDEN if headless else 0)
        self._windowed_size = config.WINDOW_SIZE
        self.fullscreen = False
        self.window = pygame.display.set_mode(self._windowed_size, self._window_flags)
        pygame.display.set_caption(config.GAME_TITLE)

        #: Everything is drawn here, at a constant resolution.
        self.screen = pygame.Surface(config.LOGICAL_SIZE).convert()

        self.clock = pygame.time.Clock()
        self._accumulator = 0.0

        #: Mouse position translated into logical coordinates.
        self.mouse_pos: tuple[int, int] = (0, 0)

    # -- scene stack --------------------------------------------------------

    @property
    def scene(self) -> Scene | None:
        """The currently active (top-most) scene."""
        return self._scenes[-1] if self._scenes else None

    def push_scene(self, scene: Scene) -> None:
        """Put ``scene`` on top of the stack and activate it."""
        if self._scenes:
            self._scenes[-1].on_exit()
        self._scenes.append(scene)
        scene.on_enter()

    def pop_scene(self) -> None:
        """Remove the top scene; quits the game when the stack runs empty."""
        if not self._scenes:
            return
        self._scenes.pop().on_exit()
        if self._scenes:
            self._scenes[-1].on_enter()
        else:
            self.quit()

    def replace_scene(self, scene: Scene) -> None:
        """Swap the top scene for ``scene``."""
        if self._scenes:
            self._scenes.pop().on_exit()
        self._scenes.append(scene)
        scene.on_enter()

    def quit(self) -> None:
        """Ask the main loop to stop after the current frame."""
        self.running = False

    # -- coordinate mapping -------------------------------------------------

    def _viewport(self) -> pygame.Rect:
        """The letterboxed rectangle inside the window that the game fills."""
        win_w, win_h = self.window.get_size()
        log_w, log_h = config.LOGICAL_SIZE
        scale = min(win_w / log_w, win_h / log_h)
        size = (round(log_w * scale), round(log_h * scale))
        return pygame.Rect(((win_w - size[0]) // 2, (win_h - size[1]) // 2), size)

    def to_logical(self, window_pos: tuple[int, int]) -> tuple[int, int]:
        """Translate a window pixel position into logical game coordinates."""
        view = self._viewport()
        log_w, log_h = config.LOGICAL_SIZE
        if view.width == 0 or view.height == 0:
            return (0, 0)
        x = (window_pos[0] - view.x) * log_w / view.width
        y = (window_pos[1] - view.y) * log_h / view.height
        return (int(x), int(y))

    # -- main loop ----------------------------------------------------------

    def toggle_fullscreen(self) -> None:
        """Switch between windowed and fullscreen.

        SDL may hand us a brand new window surface, so the cached reference has
        to be refreshed - otherwise every later frame would be drawn into a
        surface that is no longer on screen.
        """
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode(self._windowed_size, self._window_flags)

    def _process_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()
                return
            if event.type == pygame.MOUSEMOTION:
                self.mouse_pos = self.to_logical(event.pos)
            elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                self.mouse_pos = self.to_logical(event.pos)
            elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
                self._windowed_size = (event.w, event.h)
                self.window = pygame.display.set_mode(self._windowed_size, self._window_flags)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                self.toggle_fullscreen()
                continue
            if self.scene is not None:
                self.scene.handle_event(event)

    def _update(self, frame_time: float) -> None:
        """Advance the simulation in fixed steps, catching up to real time."""
        self._accumulator += min(frame_time, config.MAX_FRAME_TIME)
        scene = self.scene
        while self._accumulator >= config.FIXED_DT:
            self._accumulator -= config.FIXED_DT
            if scene is not None:
                scene.update(config.FIXED_DT)

    def _render(self) -> None:
        if self.scene is not None:
            self.scene.draw(self.screen)
        self.window.fill(config.BLACK)
        view = self._viewport()
        if view.size == config.LOGICAL_SIZE:
            self.window.blit(self.screen, view.topleft)
        else:
            pygame.transform.scale(self.screen, view.size, self.window.subsurface(view))
        pygame.display.flip()

    def step(self, frame_time: float) -> None:
        """Run exactly one frame. Split out so tests can drive the loop."""
        self._process_events()
        if not self.running:
            return
        self._update(frame_time)
        self._render()

    def run(self, initial_scene: Scene) -> None:
        """Enter the main loop with ``initial_scene`` on the stack."""
        self.push_scene(initial_scene)
        self.running = True
        try:
            while self.running:
                frame_time = self.clock.tick(config.FPS) / 1000.0
                self.step(frame_time)
        finally:
            while self._scenes:
                self._scenes.pop().on_exit()
            pygame.quit()
