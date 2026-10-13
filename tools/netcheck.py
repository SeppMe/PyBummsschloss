"""Find a message broker this network actually lets through.

Run it when a network game will not connect::

    python tools/netcheck.py                 # try the built-in list
    python tools/netcheck.py wss://host/mqtt # try one particular address

For every candidate it opens two sessions, lets them find each other, starts a
match and plays a turn - the same thing two players would do, in one process.
Whatever it reports as working can be passed to the game as ``--broker``.
"""

from __future__ import annotations

import sys
import time

from bummsschloss import config
from bummsschloss.match import Phase
from bummsschloss.matchsetup import MatchSetup
from bummsschloss.net.protocol import new_room_code
from bummsschloss.net.session import NetSession
from bummsschloss.net.transport import MqttTransport

CONNECT_WAIT = 8.0
TURN_WAIT = 15.0


def pump(sessions, seconds: float, until=None) -> None:
    """Run the sessions for a while, advancing any shot that is in the air."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        for session in sessions:
            session.poll(time.monotonic())
            match = session.match
            if match is not None and match.phase in (Phase.FLIGHT, Phase.SETTLE):
                match.update(config.FIXED_DT)
        if until is not None and until():
            return
        time.sleep(0.005)


def try_broker(address: str) -> str:
    """Play one turn across ``address``; returns an empty string if it worked."""
    room = new_room_code()
    host = NetSession(
        MqttTransport(room, address=address),
        name="Host",
        is_host=True,
        room=room,
        setup=MatchSetup.default(2),
    )
    guest = NetSession(MqttTransport(room, address=address), name="Guest", is_host=False)
    table = [host, guest]
    try:
        pump(table, CONNECT_WAIT, until=host.can_start)
        if not all(session.transport.connected for session in table):
            return host.transport.error or "no connection"
        if not host.can_start():
            return "the two never found each other"

        host.start_match()
        pump(table, 3.0, until=lambda: guest.match is not None)
        if guest.match is None:
            return "the opening position never arrived"

        host.submit_turn(weapon_index=1, angle=-42.0, power=0.85)
        pump(table, TURN_WAIT, until=lambda: guest.my_turn)
        if host.match.state_hash() != guest.match.state_hash():
            return "the two worlds drifted apart"
        return ""
    finally:
        for session in table:
            session.close()


def main(argv: list[str]) -> int:
    candidates = argv or list(config.MQTT_BROKER_CHOICES)
    working = []
    for address in candidates:
        print(f"{address} ... ", end="", flush=True)
        try:
            trouble = try_broker(address)
        except Exception as exc:  # noqa: BLE001 - a diagnostic reports anything
            trouble = f"{type(exc).__name__}: {exc}"
        if trouble:
            print(f"no ({trouble})")
        else:
            print("works")
            working.append(address)

    print()
    if working:
        print("Use one of these, the same one for everybody:")
        for address in working:
            print(f"    bummsschloss --broker {address}")
        return 0

    print("None of them got through. If you are behind a company proxy, make sure")
    print("HTTPS_PROXY is set; the game then tunnels through it like a browser.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
