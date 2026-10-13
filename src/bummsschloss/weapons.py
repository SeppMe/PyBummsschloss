"""The arsenal.

Each weapon is a small bundle of coefficients. Two of them give a weapon its
character:

``gravity_scale``
    How hard gravity pulls. A mortar shell (>1) drops like a stone, a balloon
    bomb (<1) floats lazily across the map.

``wdabhkt``
    Short for *Windabhaengigkeitskoeffizient* - the wind dependency
    coefficient. It scales how strongly the per-turn wind accelerates the
    shot sideways. A heavy iron ball barely notices the breeze (0.1), a
    balloon is at its mercy (1.8).

Weapon ``name`` strings are English source strings; they are run through
``_()`` at display time.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Weapon:
    """One entry in the arsenal."""

    key: str
    name: str
    cost: int

    #: Muzzle velocity at 100% power, in px/s.
    muzzle_speed: float = 520.0
    #: Multiplier on the global gravity.
    gravity_scale: float = 1.0
    #: Windabhaengigkeitskoeffizient - how much the wind pushes this shot.
    wdabhkt: float = 0.4

    #: Crater radius in pixels.
    blast_radius: float = 26.0
    #: Damage dealt at the centre of the blast.
    damage: float = 30.0

    #: Cluster weapons split into this many bomblets at the top of the arc.
    submunitions: int = 0
    #: Sideways spread given to those bomblets, in px/s.
    submunition_spread: float = 90.0
    #: Weapon the bomblets are made of; defaults to a generic small bomb.
    submunition_key: str | None = None

    #: Instead of digging a crater, pile earth up (for the shovel-like round).
    raises_terrain: bool = False

    @property
    def is_cluster(self) -> bool:
        return self.submunitions > 0


#: The prototype arsenal, in the order they appear in the HUD (keys 1..n).
ARSENAL: tuple[Weapon, ...] = (
    Weapon(
        key="cannonball",
        name="Cannonball",
        cost=50,
        muzzle_speed=540.0,
        gravity_scale=1.0,
        wdabhkt=0.12,
        blast_radius=24.0,
        damage=26.0,
    ),
    Weapon(
        key="mortar",
        name="Mortar shell",
        cost=180,
        muzzle_speed=470.0,
        gravity_scale=1.7,
        wdabhkt=0.25,
        blast_radius=38.0,
        damage=42.0,
    ),
    Weapon(
        key="balloon_bomb",
        name="Balloon bomb",
        cost=220,
        muzzle_speed=360.0,
        gravity_scale=0.32,
        wdabhkt=1.8,
        blast_radius=30.0,
        damage=30.0,
    ),
    Weapon(
        key="cluster",
        name="Cluster barrel",
        cost=340,
        muzzle_speed=500.0,
        gravity_scale=0.9,
        wdabhkt=0.5,
        blast_radius=16.0,
        damage=12.0,
        submunitions=5,
        submunition_spread=110.0,
        submunition_key="bomblet",
    ),
    Weapon(
        key="big_bertha",
        name="Fat Bertha",
        cost=600,
        muzzle_speed=430.0,
        gravity_scale=1.25,
        wdabhkt=0.08,
        blast_radius=62.0,
        damage=78.0,
    ),
    Weapon(
        key="molehill",
        name="Molehill",
        cost=120,
        muzzle_speed=480.0,
        gravity_scale=1.1,
        wdabhkt=0.3,
        blast_radius=34.0,
        damage=0.0,
        raises_terrain=True,
    ),
)

#: Weapons that are not selectable but can be spawned by other weapons.
HIDDEN_WEAPONS: tuple[Weapon, ...] = (
    Weapon(
        key="bomblet",
        name="Bomblet",
        cost=0,
        gravity_scale=1.0,
        wdabhkt=0.35,
        blast_radius=20.0,
        damage=16.0,
    ),
)

BY_KEY: dict[str, Weapon] = {w.key: w for w in ARSENAL + HIDDEN_WEAPONS}


def by_key(key: str) -> Weapon:
    """Look a weapon up by its stable identifier."""
    return BY_KEY[key]
