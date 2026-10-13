"""The world model: terrain, castles and projectiles.

Nothing in this package imports pygame, so the whole simulation can run
headless - in tests today and on a dedicated server once network play arrives.
"""

from bummsschloss.world.castle import Castle
from bummsschloss.world.projectile import Projectile
from bummsschloss.world.terrain import Terrain

__all__ = ["Castle", "Projectile", "Terrain"]
