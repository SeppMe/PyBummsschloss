"""The arsenal.

Each weapon is a small bundle of coefficients. Two of them give a weapon its
character:

``gravity_scale``
    How hard gravity pulls. A mortar shell (>1) drops like a stone, a balloon
    bomb (0) never comes down at all.

``wdabhkt``
    Short for *Windabhaengigkeitskoeffizient* - the wind dependency
    coefficient. It scales how strongly the per-turn wind accelerates the
    shot sideways. A heavy iron ball barely notices the breeze (0.1), a
    balloon is at its mercy (1.8), a laser ignores it entirely (0).

Weapon ``name`` and ``description`` strings are English source strings; they
are run through ``_()`` at display time.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Weapon:
    """One entry in the arsenal."""

    key: str
    name: str
    cost: int
    #: One line telling the player what makes this weapon special.
    description: str = ""

    #: Muzzle velocity at 100% power, in px/s.
    muzzle_speed: float = 520.0
    #: Multiplier on the global gravity. Zero means the shot never falls.
    gravity_scale: float = 1.0
    #: Windabhaengigkeitskoeffizient - how much the wind pushes this shot.
    wdabhkt: float = 0.4

    #: Radius in pixels within which castles are hurt.
    blast_radius: float = 26.0
    #: Damage dealt at the centre of the blast.
    damage: float = 30.0
    #: A world-shaking weapon ignores distance entirely: every castle still
    #: standing takes the full ``damage``, the shooter's own included.
    hits_everything: bool = False
    #: Crater size relative to the blast radius. An earthquake rattles every
    #: castle but barely scratches the ground, so it gets a small value.
    crater_scale: float = 1.0

    #: Cluster weapons split into this many bomblets at the top of the arc.
    submunitions: int = 0
    #: Sideways spread given to those bomblets, in px/s.
    submunition_spread: float = 90.0
    #: Weapon the bomblets are made of; defaults to a generic small bomb.
    submunition_key: str | None = None

    #: How far, in pixels, this round can dig through solid ground before it
    #: goes off. Zero means it detonates on contact like everything else.
    burrow_depth: float = 0.0
    #: Speed while underground, in px/s.
    burrow_speed: float = 210.0
    #: Upward acceleration while underground, in px/s^2. A digging round
    #: steers itself back towards the surface instead of boring straight on.
    burrow_lift: float = 0.0

    #: True if the round flies straight through the castle of whoever fired
    #: it. Weapons that are meant to be aimed at one's own feet would
    #: otherwise be impossible to use.
    ignores_own_castle: bool = False

    @property
    def is_cluster(self) -> bool:
        return self.submunitions > 0

    @property
    def burrows(self) -> bool:
        return self.burrow_depth > 0.0

    @property
    def crater_radius(self) -> float:
        return self.blast_radius * self.crater_scale


#: The arsenal, in the order they appear in the HUD (keys 1..n).
ARSENAL: tuple[Weapon, ...] = (
    Weapon(
        key="dud",
        name="Dud",
        cost=0,
        description="Free, and about as dangerous as a thrown bread roll.",
        muzzle_speed=500.0,
        gravity_scale=1.0,
        wdabhkt=0.5,
        blast_radius=10.0,
        damage=3.0,
    ),
    Weapon(
        key="cannonball",
        name="Cannonball",
        cost=50,
        description="Cheap, heavy and barely troubled by the wind.",
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
        description="Falls steeply - good for targets tucked behind a hill.",
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
        description="Never falls. Rides the wind until it bumps into something.",
        muzzle_speed=360.0,
        gravity_scale=0.0,
        wdabhkt=1.8,
        blast_radius=30.0,
        damage=30.0,
    ),
    Weapon(
        key="mole",
        name="Mole",
        cost=260,
        description="Burrows into the hill and back out. Spares the castle that fired it.",
        muzzle_speed=500.0,
        gravity_scale=1.0,
        wdabhkt=0.2,
        blast_radius=34.0,
        damage=44.0,
        burrow_depth=320.0,
        burrow_speed=210.0,
        burrow_lift=700.0,
        ignores_own_castle=True,
    ),
    Weapon(
        key="cluster",
        name="Cluster barrel",
        cost=340,
        description="Bursts at the top of its arc into five little bomblets.",
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
        key="earthquake",
        name="Earthquake",
        cost=420,
        description="Shakes the whole world. Every castle takes the same - yours too.",
        muzzle_speed=480.0,
        gravity_scale=1.0,
        wdabhkt=0.3,
        blast_radius=34.0,
        damage=18.0,
        hits_everything=True,
        crater_scale=0.7,
    ),
    Weapon(
        key="laser",
        name="Laser",
        cost=480,
        description="Flies dead straight: no gravity, no wind, no excuses.",
        muzzle_speed=1600.0,
        gravity_scale=0.0,
        wdabhkt=0.0,
        blast_radius=18.0,
        damage=38.0,
    ),
    Weapon(
        key="big_bertha",
        name="Fat Bertha",
        cost=600,
        description="A huge crater. Expensive, slow, and worth every taler.",
        muzzle_speed=430.0,
        gravity_scale=1.25,
        wdabhkt=0.08,
        blast_radius=62.0,
        damage=78.0,
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

#: The weapon a player starts a match with. The dud sits in slot 1 because it
#: is free, but the cannonball is what everybody actually reaches for first.
DEFAULT_WEAPON_KEY = "cannonball"


def index_of(key: str) -> int:
    """Position of a selectable weapon in the arsenal."""
    return next(i for i, weapon in enumerate(ARSENAL) if weapon.key == key)


#: Index of :data:`DEFAULT_WEAPON_KEY`, so the order can change freely.
DEFAULT_WEAPON_INDEX = index_of(DEFAULT_WEAPON_KEY)


def by_key(key: str) -> Weapon:
    """Look a weapon up by its stable identifier."""
    return BY_KEY[key]
