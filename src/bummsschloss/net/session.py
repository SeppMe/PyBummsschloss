"""Lockstep play over a shared postbox.

Every client runs the whole simulation itself. All that travels between them
is what a player *decided*: their weapon, angle and power. That works because
:class:`~bummsschloss.match.Match` is deterministic - same opening position,
same orders, same result.

Two things keep it honest:

* The opening position is not recomputed by anyone. The host generates it and
  ships it as a snapshot, so a difference in somebody's ``math.sin`` cannot
  grow a different mountain.
* After every turn the host publishes a short hash of the world. A client that
  does not match asks for a fresh snapshot and carries on. That costs a few
  kilobytes and spares us ever having to chase a floating-point ghost.

The session is deliberately free of pygame: the view polls it once a frame and
reads :attr:`NetSession.match`, and the tests drive two of them in a single
process over a :class:`~bummsschloss.net.transport.LoopbackBus`.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto

from bummsschloss import config
from bummsschloss.match import Match, Phase
from bummsschloss.matchsetup import MAX_NAME_LENGTH, MatchSetup, PlayerSetup
from bummsschloss.net import protocol
from bummsschloss.net.transport import Transport


class SessionState(Enum):
    """Where a session is in its life."""

    CONNECTING = auto()
    LOBBY = auto()
    PLAYING = auto()
    FAILED = auto()


@dataclass
class Peer:
    """Somebody in the room."""

    peer_id: str
    name: str
    last_seen: float = 0.0
    #: Filled in once the host has drawn up the seating.
    seat: int | None = None

    @property
    def display_name(self) -> str:
        return self.name.strip() or "?"


@dataclass
class NetSession:
    """One player's view of a networked game."""

    transport: Transport
    name: str
    is_host: bool
    room: str = ""
    #: The host's economy choices; ignored for a guest.
    setup: MatchSetup = field(default_factory=MatchSetup)
    peer_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    state: SessionState = field(init=False, default=SessionState.CONNECTING)
    peers: list[Peer] = field(init=False, default_factory=list)
    match: Match | None = field(init=False, default=None)
    #: Set when something went wrong badly enough to stop playing.
    failure: str | None = field(init=False, default=None)
    #: How often this client had to be put back in step. Shown in the HUD, and
    #: a useful smell test when tuning determinism.
    resyncs: int = field(init=False, default=0)

    _last_announce: float = field(init=False, default=-99.0)
    _trouble_since: float | None = field(init=False, default=None)
    _pending_turns: dict[int, dict] = field(init=False, default_factory=dict)
    _their_hashes: dict[int, str] = field(init=False, default_factory=dict)
    _my_hashes: dict[int, str] = field(init=False, default_factory=dict)
    _resync_wanted: bool = field(init=False, default=False)
    _owed_snapshots: set[str] = field(init=False, default_factory=set)

    def __post_init__(self) -> None:
        if self.is_host:
            self.peers = [Peer(self.peer_id, self.name)]

    # -- the view's handles -------------------------------------------------

    @property
    def my_seat(self) -> int | None:
        """Which seat this client plays, once the host has dealt them out."""
        for peer in self.peers:
            if peer.peer_id == self.peer_id:
                return peer.seat
        return None

    @property
    def seated(self) -> list[Peer]:
        """Everybody with a seat, in seat order."""
        return sorted(
            (peer for peer in self.peers if peer.seat is not None),
            key=lambda peer: peer.seat,
        )

    @property
    def my_turn(self) -> bool:
        """True while this client is the one everybody is waiting for."""
        return (
            self.match is not None
            and self.match.phase is Phase.AIM
            and self.my_seat == self.match.current_player
        )

    def waiting_for(self) -> str:
        """Name of the player whose move everybody is waiting for."""
        if self.match is None:
            return ""
        return self.match.player.name

    def can_start(self) -> bool:
        return (
            self.is_host
            and self.match is None
            and config.MIN_PLAYERS <= len(self.peers) <= config.MAX_PLAYERS
        )

    # -- driving ------------------------------------------------------------

    def poll(self, now: float) -> None:
        """Do the network's housekeeping. Call once a frame; never blocks."""
        if self.failure is None and self.transport.error and self.match is None:
            # Before the match this is fatal - but not at the first hiccup:
            # paho keeps retrying, and a broker that blinks is no reason to
            # throw everybody out of the lobby.
            if self._trouble_since is None:
                self._trouble_since = now
            elif now - self._trouble_since > config.CONNECT_TIMEOUT:
                self.failure = self.transport.error
                self.state = SessionState.FAILED
        elif not self.transport.error:
            self._trouble_since = None

        for payload in self.transport.receive():
            self._handle(payload, now)

        if self.state is SessionState.CONNECTING and self.transport.connected:
            self.state = SessionState.LOBBY

        if self.state in (SessionState.CONNECTING, SessionState.LOBBY):
            self._announce(now)
            if self.is_host:
                self._forget_silent_peers(now)

        self._drain_pending_turns()
        self._check_sync()
        self._serve_owed_snapshots()

    def start_match(self) -> bool:
        """Host only: deal the seats and send everybody the opening position."""
        if not self.can_start():
            return False
        setup = self._seated_setup()
        match = Match(setup=setup, seed=random.SystemRandom().randrange(2**31))
        self._send(
            protocol.START,
            seats=[
                {"peer": peer.peer_id, "name": peer.display_name} for peer in self.peers
            ],
            snapshot=match.snapshot(),
        )
        return True

    def submit_turn(self, weapon_index: int, angle: float, power: float) -> bool:
        """Tell everybody - this client included - what this player decided."""
        if self.match is None or not self.my_turn:
            return False
        self._send(
            protocol.TURN,
            turn=self.match.turn_number,
            seat=self.my_seat,
            weapon=int(weapon_index),
            angle=float(angle),
            power=float(power),
        )
        return True

    def close(self) -> None:
        if self.transport.connected:
            self._send(protocol.BYE)
        self.transport.close()

    # -- incoming -----------------------------------------------------------

    def _handle(self, payload: dict, now: float) -> None:
        kind = payload.get("type")
        sender = payload.get("from", "")
        mine = sender == self.peer_id

        if kind == protocol.HELLO:
            self._on_hello(payload, now)
        elif kind == protocol.LOBBY and not self.is_host:
            self._on_lobby(payload, now)
        elif kind == protocol.START:
            self._on_start(payload)
        elif kind == protocol.TURN:
            self._on_turn(payload)
        elif kind == protocol.SYNC and not mine:
            self._their_hashes[int(payload.get("turn", 0))] = payload.get("hash", "")
        elif kind == protocol.RESYNC and self.is_host and not mine:
            self._owed_snapshots.add(sender)
        elif kind == protocol.STATE and not mine:
            self._on_state(payload)
        elif kind == protocol.BYE and self.is_host and not mine:
            self._drop_peer(sender)

    def _on_hello(self, payload: dict, now: float) -> None:
        if not self.is_host:
            return
        sender = payload.get("from", "")
        name = str(payload.get("name", ""))[:MAX_NAME_LENGTH]
        for peer in self.peers:
            if peer.peer_id == sender:
                peer.last_seen = now
                if peer.name != name and name:
                    peer.name = name
                    self._announce_lobby()
                return
        if self.match is not None or len(self.peers) >= config.MAX_PLAYERS:
            # The table is full, or the game has already begun.
            return
        self.peers.append(Peer(sender, name, last_seen=now))
        self._announce_lobby()

    def _on_lobby(self, payload: dict, now: float) -> None:
        self.room = payload.get("room", self.room)
        self.peers = [
            Peer(entry["peer"], entry["name"], last_seen=now, seat=index)
            for index, entry in enumerate(payload.get("seats", []))
        ]
        if self.state is SessionState.CONNECTING:
            self.state = SessionState.LOBBY

    def _on_start(self, payload: dict) -> None:
        if self.match is not None:
            return
        seats = payload.get("seats", [])
        self.peers = [
            Peer(entry["peer"], entry["name"], seat=index) for index, entry in enumerate(seats)
        ]
        match = Match()
        match.restore(payload["snapshot"])
        self.match = match
        self.state = SessionState.PLAYING

    def _on_turn(self, payload: dict) -> None:
        if self.match is None:
            return
        turn = int(payload.get("turn", -1))
        sender = payload.get("from", "")
        seat = payload.get("seat")
        if not self._seat_belongs_to(seat, sender):
            return
        self._pending_turns[turn] = payload

    def _on_state(self, payload: dict) -> None:
        if self.match is None:
            return
        self.match.restore(payload["snapshot"])
        self._pending_turns.clear()
        self._my_hashes.clear()
        self._their_hashes.clear()
        self.resyncs += 1

    # -- outgoing -----------------------------------------------------------

    def _send(self, kind: str, **fields) -> None:
        self.transport.publish(protocol.message(kind, self.peer_id, **fields))

    def _announce(self, now: float) -> None:
        """Keep saying hello, so a late joiner is noticed and we are not dropped."""
        if now - self._last_announce < config.LOBBY_BROADCAST_INTERVAL:
            return
        self._last_announce = now
        if self.is_host:
            self._announce_lobby()
        else:
            self._send(protocol.HELLO, name=self.name)

    def _announce_lobby(self) -> None:
        self._send(
            protocol.LOBBY,
            room=self.room,
            seats=[{"peer": peer.peer_id, "name": peer.display_name} for peer in self.peers],
        )

    def _serve_owed_snapshots(self) -> None:
        """Answer resync requests, but only from a settled position."""
        if not self._owed_snapshots or self.match is None:
            return
        if self.match.phase is not Phase.AIM:
            return
        self._owed_snapshots.clear()
        self._send(protocol.STATE, snapshot=self.match.snapshot())

    # -- lockstep -----------------------------------------------------------

    def _drain_pending_turns(self) -> None:
        """Carry out an order as soon as the local match is ready for it."""
        match = self.match
        if match is None or match.phase is not Phase.AIM:
            return
        payload = self._pending_turns.pop(match.turn_number, None)
        if payload is None:
            return
        match.apply_turn(
            seat=int(payload["seat"]),
            weapon_index=int(payload["weapon"]),
            angle=float(payload["angle"]),
            power=float(payload["power"]),
        )

    def _check_sync(self) -> None:
        """Compare notes with the host about the state of the world."""
        match = self.match
        if match is None or match.phase is not Phase.AIM:
            return

        turn = match.turn_number
        if turn not in self._my_hashes:
            self._my_hashes[turn] = match.state_hash()
            if self.is_host:
                self._send(protocol.SYNC, turn=turn, hash=self._my_hashes[turn])
            self._forget_old_hashes(turn)

        if self.is_host:
            return
        theirs = self._their_hashes.get(turn)
        if theirs is None or theirs == self._my_hashes[turn]:
            self._resync_wanted = False
            return
        if not self._resync_wanted:
            # Ask once; the answer wipes the slate clean.
            self._resync_wanted = True
            self._send(protocol.RESYNC)

    def _forget_old_hashes(self, turn: int) -> None:
        for book in (self._my_hashes, self._their_hashes):
            for old in [key for key in book if key < turn - 4]:
                del book[old]

    # -- seating ------------------------------------------------------------

    def _seated_setup(self) -> MatchSetup:
        """Turn the people in the room into a match setup."""
        setup = MatchSetup(
            players=[
                PlayerSetup(name=peer.display_name, color_index=index)
                for index, peer in enumerate(self.peers)
            ],
            starting_money=self.setup.starting_money,
            turn_income=self.setup.turn_income,
            income_model=self.setup.income_model,
        )
        return setup

    def _seat_belongs_to(self, seat, sender: str) -> bool:
        """Nobody gets to fire somebody else's cannon."""
        for peer in self.peers:
            if peer.peer_id == sender:
                return peer.seat == seat
        return False

    def _drop_peer(self, peer_id: str) -> None:
        if self.match is not None or peer_id == self.peer_id:
            return
        before = len(self.peers)
        self.peers = [peer for peer in self.peers if peer.peer_id != peer_id]
        if len(self.peers) != before:
            self._announce_lobby()

    def _forget_silent_peers(self, now: float) -> None:
        stale = [
            peer
            for peer in self.peers
            if peer.peer_id != self.peer_id and now - peer.last_seen > config.PEER_TIMEOUT
        ]
        for peer in stale:
            self._drop_peer(peer.peer_id)
