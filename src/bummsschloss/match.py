"""The rules engine.

:class:`Match` owns everything that *is* the game: terrain, castles, money,
wind, whose turn it is and the shots in flight. It knows nothing about pygame,
windows or input devices, which keeps it testable today and reusable as the
authoritative server once network play arrives.

A turn runs through four phases:

``AIM``       waiting for the active player to fire
``FLIGHT``    one or more projectiles are in the air
``SETTLE``    explosions fade, undermined castles topple
``GAME_OVER`` one castle has been reduced to rubble

The caller drives everything with :meth:`Match.update`, which takes a fixed
time step so the simulation stays deterministic.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass, field
from enum import Enum, auto
from random import Random

from bummsschloss import config
from bummsschloss.matchsetup import MatchSetup
from bummsschloss.stats import MatchSummary, PlayerStats, award_winners
from bummsschloss.weapons import ARSENAL, Weapon, by_key
from bummsschloss.world.castle import Castle, wrap_delta
from bummsschloss.world.projectile import Projectile
from bummsschloss.world.terrain import Terrain


class Phase(Enum):
    AIM = auto()
    FLIGHT = auto()
    SETTLE = auto()
    GAME_OVER = auto()


@dataclass
class Player:
    """One seat at the table. For now every seat is local (hotseat)."""

    index: int
    name: str
    color_index: int = 0
    money: int = config.STARTING_MONEY
    weapon_index: int = 0
    #: Barrel angle in degrees; 0 is due east, negative points upwards.
    angle: float = -45.0
    power: float = 0.65
    stats: PlayerStats = field(default_factory=PlayerStats)

    @property
    def weapon(self) -> Weapon:
        return ARSENAL[self.weapon_index % len(ARSENAL)]

    @property
    def color(self) -> config.Color:
        return config.player_color(self.color_index)

    def can_afford(self, weapon: Weapon) -> bool:
        return self.money >= weapon.cost


@dataclass
class Explosion:
    """A short-lived blast, kept around purely so the view can draw it."""

    x: float
    y: float
    radius: float
    age: float = 0.0

    @property
    def done(self) -> bool:
        return self.age >= config.EXPLOSION_LIFETIME

    @property
    def progress(self) -> float:
        return min(1.0, self.age / config.EXPLOSION_LIFETIME)


@dataclass
class Match:
    """A single hotseat game between two or more castles."""

    width: int = config.LOGICAL_SIZE[0]
    height: int = config.LOGICAL_SIZE[1]
    seed: int | None = None
    #: The choices made in the pre-match menu. Defaults to a two-player game.
    setup: MatchSetup = field(default_factory=MatchSetup)

    terrain: Terrain = field(init=False)
    castles: list[Castle] = field(init=False, default_factory=list)
    players: list[Player] = field(init=False, default_factory=list)
    projectiles: list[Projectile] = field(init=False, default_factory=list)
    explosions: list[Explosion] = field(init=False, default_factory=list)

    phase: Phase = field(init=False, default=Phase.AIM)
    current_player: int = field(init=False, default=0)
    wind: float = field(init=False, default=0.0)
    turn_number: int = field(init=False, default=1)
    winner: int | None = field(init=False, default=None)
    #: Short message for the view, as an untranslated source string.
    last_event: str = field(init=False, default="")
    #: Filled in once the match is over.
    summary: MatchSummary | None = field(init=False, default=None)

    _settle_timer: float = field(init=False, default=0.0)
    #: Who fired the shot currently being resolved, and what it has achieved.
    _shot_owner: int | None = field(init=False, default=None)
    _shot_enemy_damage: float = field(init=False, default=0.0)
    _shot_any_damage: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        if self.seed is None:
            self.seed = self.setup.seed
        self.rng = Random(self.seed)
        self.reset()

    # -- setup --------------------------------------------------------------

    def reset(self, seed: int | None = None) -> None:
        """Generate a fresh landscape and put every castle back on its feet."""
        if seed is not None:
            self.seed = seed
        self.rng = Random(self.seed)

        self.terrain = Terrain.generate(self.width, self.height, self.rng)
        self.players = [
            Player(index=index, name=self.setup.display_name(index), color_index=seat.color_index,
                   money=self.setup.starting_money)
            for index, seat in enumerate(self.setup.players)
        ]
        self.castles = []
        spots = list(config.castle_spots(len(self.players), self.rng))
        # Which seat gets which spot is drawn as well, so player one is not
        # always the one on the left.
        self.rng.shuffle(spots)
        for index, spot in enumerate(spots):
            centre = self.width * spot
            left = int(centre - config.CASTLE_WIDTH / 2) - 4
            right = int(centre + config.CASTLE_WIDTH / 2) + 4
            level = self.terrain.flatten(
                left,
                right,
                self.terrain.average_surface(left, right),
                blend=config.CASTLE_APRON,
            )
            self.castles.append(Castle(owner=index, centre_x=centre, bottom_y=level))

        self.projectiles.clear()
        self.explosions.clear()
        self.phase = Phase.AIM
        self.current_player = 0
        self.turn_number = 1
        self.winner = None
        self.last_event = ""
        self.summary = None
        self._settle_timer = 0.0
        self._shot_owner = None
        self._shot_enemy_damage = 0.0
        self._shot_any_damage = 0.0
        self.roll_wind()
        self._grant_income(self.players[0])

    def roll_wind(self) -> None:
        """Pick a new wind for the turn."""
        self.wind = self.rng.uniform(-config.WIND_MAX, config.WIND_MAX)

    # -- convenience --------------------------------------------------------

    @property
    def player(self) -> Player:
        return self.players[self.current_player]

    @property
    def castle(self) -> Castle:
        return self.castles[self.current_player]

    def castle_of(self, player_index: int) -> Castle:
        return self.castles[player_index]

    def opponent_of(self, player_index: int) -> int:
        """The next seat clockwise. With more than two players this is simply
        the neighbour, not "the enemy" - use :meth:`living_opponents` for that.
        """
        return (player_index + 1) % len(self.players)

    def living_players(self) -> list[int]:
        return [castle.owner for castle in self.castles if castle.alive]

    def living_opponents(self, player_index: int) -> list[int]:
        return [index for index in self.living_players() if index != player_index]

    @property
    def round_number(self) -> int:
        """Full rounds played so far, counting from 1."""
        return (self.turn_number - 1) // max(1, len(self.players)) + 1

    # -- aiming -------------------------------------------------------------

    def aim_at(self, x: float, y: float) -> None:
        """Point the active barrel towards a world position."""
        muzzle_x, muzzle_y = self.castle.muzzle
        dx = wrap_delta(x - muzzle_x, self.width)
        dy = y - muzzle_y
        self.player.angle = math.degrees(math.atan2(dy, dx))

    def adjust_angle(self, degrees: float) -> None:
        self.player.angle = max(-180.0, min(0.0, self.player.angle + degrees))

    def adjust_power(self, delta: float) -> None:
        self.player.power = max(
            config.MIN_POWER, min(config.MAX_POWER, self.player.power + delta)
        )

    def select_weapon(self, index: int) -> None:
        if 0 <= index < len(ARSENAL):
            self.player.weapon_index = index

    def cycle_weapon(self, step: int = 1) -> None:
        self.player.weapon_index = (self.player.weapon_index + step) % len(ARSENAL)

    # -- firing -------------------------------------------------------------

    def can_fire(self) -> bool:
        return self.phase is Phase.AIM and self.player.can_afford(self.player.weapon)

    def fire(self) -> bool:
        """Launch the active player's shot. Returns False if it was not possible."""
        if not self.can_fire():
            return False

        player = self.player
        weapon = player.weapon
        player.money -= weapon.cost
        player.stats.shots_fired += 1
        player.stats.money_spent += weapon.cost

        self._shot_owner = player.index
        self._shot_enemy_damage = 0.0
        self._shot_any_damage = 0.0

        angle = math.radians(player.angle)
        speed = weapon.muzzle_speed * player.power
        muzzle_x, muzzle_y = self.castle.muzzle
        self.projectiles.append(
            Projectile(
                x=muzzle_x + math.cos(angle) * 18,
                y=muzzle_y + math.sin(angle) * 18,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                weapon=weapon,
                owner=player.index,
            )
        )
        self.phase = Phase.FLIGHT
        self.last_event = ""
        return True

    # -- simulation ---------------------------------------------------------

    def update(self, dt: float) -> None:
        """Advance the match by one fixed time step."""
        for explosion in self.explosions:
            explosion.age += dt
        self.explosions = [e for e in self.explosions if not e.done]

        if self.phase is Phase.FLIGHT:
            self._update_projectiles(dt)
            if not self.projectiles:
                self.phase = Phase.SETTLE
                self._settle_timer = 0.0
        elif self.phase is Phase.SETTLE:
            self._update_settling(dt)

    def _update_projectiles(self, dt: float) -> None:
        survivors: list[Projectile] = []
        for projectile in self.projectiles:
            if projectile.expired or self._gone_for_good(projectile):
                self.last_event = "The shot was lost in the clouds."
                continue

            previous = (projectile.x, projectile.y)
            projectile.step(dt, self.wind)

            if projectile.weapon.is_cluster and projectile.can_split and projectile.past_apex:
                self._split(projectile, survivors)
                continue

            impact = self._impact_point(previous, (projectile.x, projectile.y), projectile)
            if impact is not None:
                self._detonate(projectile, *impact)
            elif projectile.burrow_exhausted:
                # The mole has dug as far as it can; it goes off where it is.
                self.last_event = "The mole goes off underground!"
                self._detonate(projectile, projectile.x, projectile.y)
            else:
                survivors.append(projectile)
        self.projectiles = survivors

    def _gone_for_good(self, projectile: Projectile) -> bool:
        """True for a shot that can provably never return to the playfield.

        A weapon with no gravity that is above the sky and not descending will
        never come back down. Retiring it at once saves the table from waiting
        out the full flight timer.
        """
        return (
            projectile.weapon.gravity_scale == 0.0
            and projectile.vy <= 0.0
            and projectile.y < -config.LOST_IN_SKY_MARGIN
        )

    def _impact_point(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        projectile: Projectile,
    ) -> tuple[float, float] | None:
        """Walk the movement segment pixel by pixel, looking for a hit.

        Sampling the whole segment rather than only the end point stops fast
        shots from tunnelling through thin ridges or castle walls.
        """
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        steps = max(1, int(max(abs(dx), abs(dy))))
        for i in range(1, steps + 1):
            t = i / steps
            x = start[0] + dx * t
            y = start[1] + dy * t
            # Above the sky or below the world is not a collision; the shot
            # keeps flying out of sight and may well come back.
            if y < 0:
                continue
            for castle in self.castles:
                if not castle.alive:
                    continue
                if castle.owner == projectile.owner and projectile.weapon.ignores_own_castle:
                    # Some rounds are meant to be fired at one's own feet.
                    continue
                if castle.contains(x, y, self.width):
                    return (x, y)
            if self.terrain.is_solid(x, y):
                if projectile.can_burrow:
                    # A digging round bites into the hill instead of stopping.
                    projectile.start_burrowing()
                    continue
                if not projectile.burrowing:
                    return (x, y)
                continue
            if projectile.burrowing:
                # It has dug its way back out into the open air.
                projectile.stop_burrowing()
            if y > self.height + 2000:
                # Fell out of the world entirely - treat as a dud.
                self.last_event = "The shot vanished into the abyss."
                return (x, min(y, self.height))
        return None

    def _split(self, parent: Projectile, output: list[Projectile]) -> None:
        """Turn a cluster round into a handful of bomblets at the top of its arc."""
        weapon = parent.weapon
        bomblet = by_key(weapon.submunition_key or "bomblet")
        count = weapon.submunitions
        for i in range(count):
            offset = (i - (count - 1) / 2) / max(1, count - 1) * 2.0
            output.append(
                Projectile(
                    x=parent.x,
                    y=parent.y,
                    vx=parent.vx + offset * weapon.submunition_spread,
                    vy=parent.vy - abs(offset) * 20.0,
                    weapon=bomblet,
                    owner=parent.owner,
                    can_split=False,
                )
            )
        self.last_event = "The cluster barrel bursts open!"

    def _detonate(self, projectile: Projectile, x: float, y: float) -> None:
        """Resolve an impact: reshape the ground and hurt nearby castles."""
        weapon = projectile.weapon
        x = self.terrain.wrap_x(x)

        before = self.terrain.heights()
        self.terrain.explode(x, y, weapon.crater_radius)
        self._credit_terrain_change(before)
        self.explosions.append(Explosion(x=x, y=y, radius=weapon.blast_radius))

        if weapon.hits_everything:
            self._shake_the_world(weapon, projectile.owner)
        elif weapon.damage > 0:
            for castle in self.castles:
                if not castle.alive:
                    continue
                distance = castle.distance_to(x, y, self.width)
                if distance > weapon.blast_radius:
                    continue
                falloff = 1.0 - distance / weapon.blast_radius
                self._apply_damage(castle, weapon.damage * falloff, projectile.owner)

    def _shake_the_world(self, weapon: Weapon, owner: int) -> None:
        """Hit every castle still standing for the same amount, distance be damned."""
        for castle in self.castles:
            if not castle.alive:
                continue
            self.explosions.append(
                Explosion(x=castle.centre_x, y=castle.top_y, radius=weapon.blast_radius)
            )
            self._apply_damage(castle, weapon.damage, owner)
        # Said last so it is not overwritten by the per-castle messages.
        self.last_event = "The earth shakes - nobody is spared!"

    def _credit_terrain_change(self, before: list[float]) -> None:
        """Add the amount of landscape just rearranged to the shooter's tally."""
        if self._shot_owner is None:
            return
        moved = sum(abs(a - b) for a, b in zip(before, self.terrain.heights(), strict=True))
        self.players[self._shot_owner].stats.terrain_moved += moved / 32.0

    def _apply_damage(
        self,
        castle: Castle,
        amount: float,
        source: int | None,
        *,
        from_collapse: bool = False,
    ) -> float:
        """The single place damage is dealt, so every point gets attributed."""
        was_alive = castle.alive
        dealt = castle.damage(amount)
        if dealt <= 0:
            return 0.0

        self._shot_any_damage += dealt
        if source is not None:
            stats = self.players[source].stats
            own_castle = castle.owner == source
            if own_castle:
                stats.self_damage += dealt
                self.last_event = "Ouch - that was your own castle!"
            else:
                stats.damage_dealt += dealt
                self._shot_enemy_damage += dealt
                self.last_event = (
                    "The ground gives way!" if from_collapse else "Direct hit!"
                )
            if from_collapse:
                stats.collapse_damage += dealt
            if was_alive and not castle.alive:
                if own_castle:
                    stats.self_destructs += 1
                else:
                    stats.kills += 1
                self.last_event = "A castle falls to rubble!"
        return dealt

    def _finish_shot(self) -> None:
        """Book the result of the shot that has just finished resolving."""
        if self._shot_owner is None:
            return
        stats = self.players[self._shot_owner].stats
        if self._shot_enemy_damage > 0:
            stats.shots_hit += 1
            stats.best_shot = max(stats.best_shot, self._shot_enemy_damage)
        elif self._shot_any_damage <= 0:
            stats.shots_wasted += 1
        self._shot_owner = None
        self._shot_enemy_damage = 0.0
        self._shot_any_damage = 0.0

    def _update_settling(self, dt: float) -> None:
        """Let undermined castles fall, then hand over to the next player."""
        still_moving = False
        for castle in self.castles:
            if not castle.alive:
                continue
            if castle.update(dt, self.terrain):
                still_moving = True
            pending = castle.take_pending_fall_damage()
            if pending > 0:
                self._apply_damage(castle, pending, self._shot_owner, from_collapse=True)

        if still_moving or self.explosions:
            self._settle_timer = 0.0
            return

        self._settle_timer += dt
        if self._settle_timer < config.TURN_HANDOVER_DELAY:
            return

        self._finish_shot()
        if self._check_game_over():
            return
        self.next_turn()

    def _check_game_over(self) -> bool:
        survivors = [castle for castle in self.castles if castle.alive]
        if len(survivors) > 1:
            return False
        self.winner = survivors[0].owner if len(survivors) == 1 else None
        self.phase = Phase.GAME_OVER
        self.last_event = "Victory!" if self.winner is not None else "Everyone lost."
        self.summary = self.build_summary()
        return True

    def build_summary(self) -> MatchSummary:
        """Collect the numbers and awards for the post-match screen."""
        stats = [player.stats for player in self.players]
        return MatchSummary(
            winner=self.winner,
            turns=self.turn_number,
            player_names=[player.name for player in self.players],
            color_indices=[player.color_index for player in self.players],
            stats=stats,
            awards=award_winners(stats),
        )

    def next_turn(self) -> None:
        """Hand the cannon to the next player still standing and reroll the wind."""
        count = len(self.players)
        for offset in range(1, count + 1):
            candidate = (self.current_player + offset) % count
            if self.castles[candidate].alive:
                self.current_player = candidate
                break
        self.turn_number += 1
        self.roll_wind()
        self._grant_income(self.player)
        self.phase = Phase.AIM

    def _grant_income(self, player: Player) -> None:
        """Pay a player their lump sum for the turn they are about to take."""
        castle = self.castles[player.index]
        health = castle.hp / castle.max_hp if castle.max_hp else 0.0
        player.money += self.setup.income_for(
            round_number=self.round_number, health_fraction=health
        )

    # -- helpers for the view ----------------------------------------------

    def predicted_muzzle_velocity(self) -> tuple[float, float]:
        """Velocity the active player's shot would start with right now."""
        angle = math.radians(self.player.angle)
        speed = self.player.weapon.muzzle_speed * self.player.power
        return (math.cos(angle) * speed, math.sin(angle) * speed)

    # -- network play -------------------------------------------------------

    def apply_turn(self, seat: int, weapon_index: int, angle: float, power: float) -> bool:
        """Carry out one player's turn, wherever the order came from.

        This is the single entry point for a networked turn: the remote
        player's aim is copied onto their seat and the shot goes off, so every
        client runs exactly the same simulation from here on.
        """
        if self.phase is not Phase.AIM or seat != self.current_player:
            return False
        player = self.players[seat]
        player.weapon_index = weapon_index % len(ARSENAL)
        player.angle = float(angle)
        player.power = float(power)
        return self.fire()

    def snapshot(self) -> dict:
        """The whole match as plain data, enough to continue play from.

        Shots in flight are deliberately left out: snapshots are taken between
        turns, when the only thing moving is the players' nerves.
        """
        return {
            "seed": self.seed,
            "setup": self.setup.to_dict(),
            "terrain": self.terrain.heights(),
            "castles": [
                {
                    "owner": castle.owner,
                    "centre_x": castle.centre_x,
                    "bottom_y": castle.bottom_y,
                    "hp": castle.hp,
                }
                for castle in self.castles
            ],
            "players": [
                {
                    "name": player.name,
                    "color_index": player.color_index,
                    "money": player.money,
                    "weapon_index": player.weapon_index,
                    "angle": player.angle,
                    "power": player.power,
                    "stats": asdict(player.stats),
                }
                for player in self.players
            ],
            "phase": self.phase.name,
            "current_player": self.current_player,
            "wind": self.wind,
            "turn_number": self.turn_number,
            "winner": self.winner,
            # The random state travels too, so the next wind roll agrees.
            "rng": _encode_rng(self.rng),
        }

    def restore(self, data: dict) -> None:
        """Replace everything with the contents of a snapshot."""
        self.seed = data["seed"]
        self.setup = MatchSetup.from_dict(data["setup"])
        self.terrain = Terrain(self.width, self.height, data["terrain"])
        self.castles = [
            Castle(
                owner=entry["owner"],
                centre_x=entry["centre_x"],
                bottom_y=entry["bottom_y"],
                hp=entry["hp"],
            )
            for entry in data["castles"]
        ]
        self.players = []
        for index, entry in enumerate(data["players"]):
            player = Player(
                index=index,
                name=entry["name"],
                color_index=entry["color_index"],
                money=entry["money"],
                weapon_index=entry["weapon_index"],
                angle=entry["angle"],
                power=entry["power"],
                stats=PlayerStats(**entry["stats"]),
            )
            self.players.append(player)

        self.projectiles.clear()
        self.explosions.clear()
        self.phase = Phase[data["phase"]]
        self.current_player = data["current_player"]
        self.wind = data["wind"]
        self.turn_number = data["turn_number"]
        self.winner = data["winner"]
        self.last_event = ""
        self.summary = self.build_summary() if self.phase is Phase.GAME_OVER else None
        self._settle_timer = 0.0
        self._shot_owner = None
        self._shot_enemy_damage = 0.0
        self._shot_any_damage = 0.0
        _decode_rng(self.rng, data["rng"])

    def state_hash(self) -> str:
        """A short fingerprint of everything that matters for future play.

        Clients compare these after every turn. Values are rounded first: a
        last-bit difference in somebody's ``sin`` is not worth a resync, but
        anything a player could notice shows up here.
        """
        parts = [
            f"{self.turn_number}:{self.current_player}:{self.phase.name}",
            f"{self.wind:.2f}",
            ",".join(f"{height:.2f}" for height in self.terrain.heights()),
            ",".join(f"{castle.centre_x:.2f}|{castle.bottom_y:.2f}|{castle.hp:.2f}"
                     for castle in self.castles),
            ",".join(f"{player.money}" for player in self.players),
        ]
        return hashlib.sha256("/".join(parts).encode()).hexdigest()[:16]


def _encode_rng(rng: Random) -> list:
    """``Random.getstate`` as something JSON can carry."""
    version, internal, gauss = rng.getstate()
    return [version, list(internal), gauss]


def _decode_rng(rng: Random, data: list) -> None:
    version, internal, gauss = data
    rng.setstate((version, tuple(internal), gauss))
