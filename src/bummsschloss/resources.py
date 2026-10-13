"""Locating and loading bundled data files.

Assets live in ``src/bummsschloss/assets`` and are shipped inside the wheel as
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


def clear_cache() -> None:
    """Drop all cached assets.

    Surfaces and fonts belong to the pygame session that created them, so the
    caches have to be emptied whenever pygame is initialised afresh - otherwise
    a restarted game would draw with handles that are no longer valid.
    """
    load_image.cache_clear()
    load_font.cache_clear()
