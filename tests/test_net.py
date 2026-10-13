"""Tests for lockstep network play, driven through an in-process bus."""

from __future__ import annotations

import pytest

from bummsschloss import config
from bummsschloss.match import Phase
from bummsschloss.matchsetup import MatchSetup
from bummsschloss.net import protocol
from bummsschloss.net.session import NetSession, SessionState
from bummsschloss.net.transport import LoopbackBus


class Table:
    """A host and a number of guests sharing one bus."""

    def __init__(self, guests: int = 1) -> None:
        self.bus = LoopbackBus()
        self.clock = 0.0
        self.host = NetSession(
            self.bus.connect("host"),
            name="Host",
            is_host=True,
            room="TEST7",
            setup=MatchSetup.default(2),
        )
        self.guests = [
            NetSession(self.bus.connect(f"guest{i}"), name=f"Guest {i + 1}", is_host=False)
            for i in range(guests)
        ]

    @property
    def everyone(self) -> list[NetSession]:
        return [self.host, *self.guests]

    def poll(self, rounds: int = 4, step: float = 0.1) -> None:
        for _round in range(rounds):
            self.clock += step
            for session in self.everyone:
                session.poll(self.clock)

    def settle(self, limit: int = 20000) -> None:
        """Run every match to the end of the current turn, polling as we go.

        Messages take a poll or two to go round, so we only call it done after
        a few quiet frames in a row.
        """
        quiet = 0
        for _step in range(limit):
            self.poll(rounds=1, step=config.FIXED_DT)
            busy = False
            for session in self.everyone:
                if session.match is None:
                    continue
                if session.match.phase in (Phase.FLIGHT, Phase.SETTLE):
                    session.match.update(config.FIXED_DT)
                    busy = True
            quiet = 0 if busy else quiet + 1
            if quiet >= 8:
                return
        raise AssertionError("the turn never resolved")

    def gather_round(self) -> None:
        """Let everybody say hello and the host deal the seats."""
        self.poll(rounds=6)


@pytest.fixture
def table() -> Table:
    return Table()


# -- the lobby ---------------------------------------------------------------


def test_a_guest_is_seated_by_the_host(table):
    table.gather_round()
    assert [peer.display_name for peer in table.host.peers] == ["Host", "Guest 1"]
    assert table.guests[0].my_seat == 1
    assert table.guests[0].state is SessionState.LOBBY


def test_the_table_does_not_take_more_than_four(table):
    extra = [
        NetSession(table.bus.connect(f"extra{i}"), name=f"Extra {i}", is_host=False)
        for i in range(5)
    ]
    table.guests.extend(extra)
    table.gather_round()
    assert len(table.host.peers) == config.MAX_PLAYERS


def test_a_guest_who_goes_quiet_loses_their_seat(table):
    table.gather_round()
    assert len(table.host.peers) == 2

    # Only the host keeps talking.
    for _step in range(40):
        table.clock += 1.0
        table.host.poll(table.clock)
    assert [peer.display_name for peer in table.host.peers] == ["Host"]


def test_saying_goodbye_frees_the_seat(table):
    table.gather_round()
    table.guests[0].close()
    table.poll()
    assert [peer.display_name for peer in table.host.peers] == ["Host"]


def test_a_guest_cannot_start_the_match(table):
    table.gather_round()
    assert not table.guests[0].can_start()
    assert not table.guests[0].start_match()


# -- starting ----------------------------------------------------------------


def test_everybody_begins_from_the_very_same_world(table):
    table.gather_round()
    assert table.host.start_match()
    table.poll()

    assert table.host.match is not None
    assert table.guests[0].match is not None
    assert table.host.match.state_hash() == table.guests[0].match.state_hash()
    assert table.host.match.terrain.heights() == table.guests[0].match.terrain.heights()
    assert all(session.state is SessionState.PLAYING for session in table.everyone)


def test_the_seats_carry_the_players_names(table):
    table.gather_round()
    table.host.start_match()
    table.poll()

    names = [player.name for player in table.host.match.players]
    assert names == ["Host", "Guest 1"]
    assert table.host.my_seat == 0
    assert table.guests[0].my_seat == 1


def test_a_lone_host_cannot_start(table):
    table.host.poll(1.0)
    assert not table.host.can_start()


# -- playing -----------------------------------------------------------------


def started(guests: int = 1) -> Table:
    table = Table(guests)
    table.gather_round()
    table.host.start_match()
    table.poll()
    return table


def test_a_turn_is_replayed_by_everyone():
    table = started()
    assert table.host.my_turn
    assert not table.guests[0].my_turn

    assert table.host.submit_turn(weapon_index=1, angle=-40.0, power=0.9)
    table.poll()
    assert all(session.match.phase is Phase.FLIGHT for session in table.everyone)

    table.settle()
    host, guest = table.host.match, table.guests[0].match
    assert host.state_hash() == guest.state_hash()
    assert host.turn_number == guest.turn_number == 2
    assert [castle.hp for castle in host.castles] == [castle.hp for castle in guest.castles]


def test_only_the_player_whose_turn_it_is_may_fire():
    table = started()
    assert not table.guests[0].submit_turn(weapon_index=1, angle=-40.0, power=0.9)
    table.poll()
    assert table.host.match.phase is Phase.AIM


def test_an_order_for_somebody_elses_seat_is_ignored():
    table = started()
    # A client lying about which seat it is firing from.
    table.guests[0].transport.publish(
        protocol.message(
            protocol.TURN,
            table.guests[0].peer_id,
            turn=1,
            seat=0,
            weapon=1,
            angle=-40.0,
            power=0.9,
        )
    )
    table.poll()
    assert table.host.match.phase is Phase.AIM


def test_the_turn_passes_to_the_guest():
    table = started()
    table.host.submit_turn(weapon_index=0, angle=-45.0, power=0.5)
    table.settle()

    assert not table.host.my_turn
    assert table.guests[0].my_turn
    assert table.guests[0].submit_turn(weapon_index=0, angle=-45.0, power=0.5)
    table.settle()
    assert table.host.match.turn_number == 3


def test_an_order_that_arrives_early_is_held_back():
    """A guest still watching turn one must not drop turn two on the floor."""
    table = started()
    guest = table.guests[0]
    table.bus.paused.add(guest.transport)

    table.host.submit_turn(weapon_index=0, angle=-45.0, power=0.5)
    table.poll()
    assert guest.match.phase is Phase.AIM, "the guest should not have heard yet"

    table.bus.paused.discard(guest.transport)
    table.settle()
    assert guest.match.state_hash() == table.host.match.state_hash()


# -- putting a client back in step -------------------------------------------


def test_a_client_that_drifts_is_sent_a_fresh_world():
    table = started()
    guest = table.guests[0]

    # Something impossible happened to the guest's copy of the world.
    guest.match.castles[1].hp = 3.0
    assert guest.match.state_hash() != table.host.match.state_hash()

    table.host.submit_turn(weapon_index=0, angle=-45.0, power=0.5)
    table.settle()
    table.poll(rounds=6)

    assert guest.resyncs == 1
    assert guest.match.state_hash() == table.host.match.state_hash()


def test_a_match_in_step_is_never_resynced():
    table = started()
    for _turn in range(4):
        active = table.host if table.host.my_turn else table.guests[0]
        active.submit_turn(weapon_index=0, angle=-45.0, power=0.6)
        table.settle()
    table.poll(rounds=4)
    assert table.guests[0].resyncs == 0
    assert table.host.match.state_hash() == table.guests[0].match.state_hash()


# -- plumbing ----------------------------------------------------------------


def test_a_broken_connection_fails_the_session():
    table = Table()

    class Broken:
        connected = False
        error = "no route to host"

        def publish(self, payload):
            pass

        def receive(self):
            return []

        def close(self):
            pass

    table.host.transport = Broken()
    table.host.poll(1.0)
    assert table.host.state is not SessionState.FAILED, "one hiccup is not a failure"
    table.host.poll(1.0 + config.CONNECT_TIMEOUT + 1.0)
    assert table.host.state is SessionState.FAILED
    assert table.host.failure == "no route to host"


def test_room_codes_avoid_the_letters_people_confuse():
    code = protocol.new_room_code()
    assert len(code) == protocol.ROOM_CODE_LENGTH
    assert not set(code) & set("O0I1")
    assert protocol.clean_room_code(" test7 ") == "TEST7"


def test_messages_from_another_protocol_version_are_dropped():
    payload = protocol.message(protocol.HELLO, "abc", name="x")
    payload["v"] = protocol.PROTOCOL_VERSION + 1
    assert protocol.decode(protocol.encode(payload)) is None
    assert protocol.decode(b"not json at all") is None
