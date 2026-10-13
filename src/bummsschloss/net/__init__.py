"""Network play.

Everything in here is free of pygame, and of any assumption about *how* the
bytes travel: :mod:`~bummsschloss.net.session` drives a lockstep game through
a :class:`~bummsschloss.net.transport.Transport`, which is a public MQTT
broker in a real game and a loopback bus in the tests.
"""

from bummsschloss.net.session import NetSession, SessionState
from bummsschloss.net.transport import LoopbackBus, MqttTransport, Transport

__all__ = [
    "LoopbackBus",
    "MqttTransport",
    "NetSession",
    "SessionState",
    "Transport",
]
