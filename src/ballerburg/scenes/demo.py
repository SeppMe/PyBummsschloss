"""A throw-away demo scene used to sanity-check the engine skeleton.

It shows the pieces the real game will be built from:

* a fixed-step physics simulation (gravity, bouncing, drag)
* flat 2D drawing at a fixed logical resolution
* mouse aiming plus click-to-fire, and keyboard input
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import pygame

from ballerburg import config
from ballerburg.resources import load_font
from ballerburg.scenes.base import Scene

GROUND_Y = config.LOGICAL_SIZE[1] - 80
CANNON_POS = (90, GROUND_Y)
MAX_POWER = 520.0
TRAIL_LENGTH = 48


@dataclass
class Ball:
    """A point mass that bounces around the playfield."""

    x: float
    y: float
    vx: float
    vy: float
    radius: float
    color: config.Color
    bounciness: float = 0.62
    trail: list[tuple[float, float]] = field(default_factory=list)
    alive: bool = True

    def update(self, dt: float) -> None:
        self.vy += config.GRAVITY * dt
        self.x += self.vx * dt
        self.y += self.vy * dt

        width = config.LOGICAL_SIZE[0]
        if self.x - self.radius < 0:
            self.x = self.radius
            self.vx = -self.vx * self.bounciness
        elif self.x + self.radius > width:
            self.x = width - self.radius
            self.vx = -self.vx * self.bounciness

        if self.y + self.radius > GROUND_Y:
            self.y = GROUND_Y - self.radius
            self.vy = -self.vy * self.bounciness
            self.vx *= 0.88
            # Once it barely moves, let it come to rest and then expire.
            if abs(self.vy) < 24.0:
                self.vy = 0.0
                if abs(self.vx) < 6.0:
                    self.vx = 0.0
                    self.alive = False

        self.trail.append((self.x, self.y))
        if len(self.trail) > TRAIL_LENGTH:
            del self.trail[0]

    def draw(self, surface: pygame.Surface) -> None:
        for i, (tx, ty) in enumerate(self.trail):
            fade = (i + 1) / len(self.trail)
            tint = tuple(int(c * fade * 0.55) for c in self.color)
            radius = max(1, int(self.radius * fade * 0.5))
            pygame.draw.circle(surface, tint, (int(tx), int(ty)), radius)
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), int(self.radius))
        pygame.draw.circle(surface, config.WHITE, (int(self.x), int(self.y)), int(self.radius), 1)


class DemoScene(Scene):
    """Aim with the mouse, click to fire, watch the ball arc and bounce."""

    def on_enter(self) -> None:
        self.font = load_font(18)
        self.big_font = load_font(34)
        self.balls: list[Ball] = []
        self.power = 0.6
        self.show_help = True
        self.palette = [config.ACCENT, config.RED, config.BLUE, config.WHITE]
        self._colour_index = 0
        self.fire(math.radians(-45), MAX_POWER * 0.7)

    # -- input --------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_q):
                self.app.quit()
            elif event.key == pygame.K_SPACE:
                self.fire(self.aim_angle(), self.power * MAX_POWER)
            elif event.key == pygame.K_c:
                self.balls.clear()
            elif event.key == pygame.K_h:
                self.show_help = not self.show_help
            elif event.key == pygame.K_r:
                self.scatter()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.fire(self.aim_angle(), self.power * MAX_POWER)
        elif event.type == pygame.MOUSEWHEEL:
            self.power = max(0.1, min(1.0, self.power + event.y * 0.05))

    def aim_angle(self) -> float:
        """Angle in radians from the cannon towards the mouse cursor."""
        mx, my = self.app.mouse_pos
        return math.atan2(my - CANNON_POS[1], mx - CANNON_POS[0])

    # -- simulation ---------------------------------------------------------

    def fire(self, angle: float, speed: float) -> None:
        color = self.palette[self._colour_index % len(self.palette)]
        self._colour_index += 1
        self.balls.append(
            Ball(
                x=CANNON_POS[0] + math.cos(angle) * 40,
                y=CANNON_POS[1] + math.sin(angle) * 40,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                radius=7,
                color=color,
            )
        )

    def scatter(self) -> None:
        """Drop a handful of random balls, just to see many objects at once."""
        for _ in range(12):
            self.balls.append(
                Ball(
                    x=random.uniform(100, config.LOGICAL_SIZE[0] - 100),
                    y=random.uniform(60, 220),
                    vx=random.uniform(-160, 160),
                    vy=random.uniform(-40, 40),
                    radius=random.uniform(4, 10),
                    color=random.choice(self.palette),
                )
            )

    def update(self, dt: float) -> None:
        for ball in self.balls:
            ball.update(dt)
        self.balls = [b for b in self.balls if b.alive][-80:]

    # -- rendering ----------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_background(surface)
        self._draw_cannon(surface)
        for ball in self.balls:
            ball.draw(surface)
        self._draw_hud(surface)

    def _draw_background(self, surface: pygame.Surface) -> None:
        width, height = surface.get_size()
        # Cheap vertical gradient: a handful of bands, not a per-pixel loop.
        bands = 24
        band_h = GROUND_Y // bands
        for i in range(bands):
            t = i / (bands - 1)
            color = tuple(
                int(config.SKY[c] + (config.SKY_LOW[c] - config.SKY[c]) * t) for c in range(3)
            )
            pygame.draw.rect(surface, color, (0, i * band_h, width, band_h + 1))
        pygame.draw.rect(surface, config.GROUND, (0, GROUND_Y, width, height - GROUND_Y))
        pygame.draw.rect(surface, config.GROUND_DARK, (0, GROUND_Y, width, 4))

    def _draw_cannon(self, surface: pygame.Surface) -> None:
        angle = self.aim_angle()
        base = pygame.Rect(0, 0, 44, 26)
        base.midbottom = CANNON_POS
        pygame.draw.rect(surface, config.STONE, base)
        pygame.draw.rect(surface, config.GREY, base, 2)

        pivot = (CANNON_POS[0], CANNON_POS[1] - 18)
        tip = (pivot[0] + math.cos(angle) * 46, pivot[1] + math.sin(angle) * 46)
        pygame.draw.line(surface, config.GREY, pivot, tip, 7)
        pygame.draw.circle(surface, config.STONE, pivot, 9)

        # Dotted preview of the trajectory at the current power setting.
        speed = self.power * MAX_POWER
        vx, vy = math.cos(angle) * speed, math.sin(angle) * speed
        for step in range(1, 26):
            t = step * 0.05
            px = pivot[0] + vx * t
            py = pivot[1] + vy * t + 0.5 * config.GRAVITY * t * t
            if py > GROUND_Y or not (0 <= px <= surface.get_width()):
                break
            pygame.draw.circle(surface, config.WHITE, (int(px), int(py)), 1)

    def _draw_hud(self, surface: pygame.Surface) -> None:
        title = self.big_font.render("Ballerburg - engine demo", True, config.ACCENT)
        surface.blit(title, (20, 16))

        bar = pygame.Rect(20, 60, 180, 12)
        pygame.draw.rect(surface, config.GREY, bar, 1)
        fill = bar.inflate(-4, -4)
        fill.width = int(fill.width * self.power)
        pygame.draw.rect(surface, config.ACCENT, fill)
        label = self.font.render(
            f"power {self.power * 100:3.0f}%   balls {len(self.balls)}   "
            f"{self.app.clock.get_fps():4.0f} fps",
            True,
            config.WHITE,
        )
        surface.blit(label, (20, 80))

        if self.show_help:
            lines = [
                "mouse      aim",
                "click/space fire",
                "wheel      power",
                "R          scatter balls",
                "C          clear",
                "F11        fullscreen",
                "H          hide this help",
                "Esc/Q      quit",
            ]
            for i, line in enumerate(lines):
                text = self.font.render(line, True, config.WHITE)
                surface.blit(text, (surface.get_width() - 210, 20 + i * 22))
