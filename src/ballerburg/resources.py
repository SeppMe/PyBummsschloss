"""Locating and loading bundled data files.

Assets live in ``src/ballerburg/assets`` and are shipped inside the wheel as
package data. ``asset_path`` also understands being frozen by PyInstaller.
"""

from __future__ import annotations

import sys
from functools import cache
from pathlib import Path

import pygame


def assets_root() -> Path:
    """Return the directory that contains the bundled asset files."""
    if getattr(sys, "frozen", False):  # PyInstaller one-file / one-folder build
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "assets"
    return Path(__file__).resolve().parent / "assets"


def asset_path(*parts: str) -> Path:
    """Return the full path of an asset, e.g. ``asset_path("sprites", "ball.png")``."""
    return assets_root().joinpath(*parts)


@cache
def load_image(*parts: str, alpha: bool = True) -> pygame.Surface:
    """Load an image from the asset folder, cached by name."""
    surface = pygame.image.load(asset_path(*parts))
    return surface.convert_alpha() if alpha else surface.convert()


@cache
def load_font(size: int, *parts: str) -> pygame.font.Font:
    """Load a bundled font, or pygame's default font when no name is given."""
    name = str(asset_path(*parts)) if parts else None
    return pygame.font.Font(name, size)
