"""How the messages travel.

The game never talks to a broker directly; it talks to a
:class:`Transport`, which is either a real MQTT connection or, in the tests,
an in-process bus. Both have the same manners:

* :meth:`Transport.publish` sends a message to *everyone in the room,
  including the sender*. The echo is on purpose - it means every client, the
  one that pressed fire included, learns about a turn the same way, and there
  is only one code path to get wrong.
* :meth:`Transport.receive` hands over whatever has arrived since last time
  and never blocks, so a game loop can poll it once a frame.

Using a public broker is what saves us from port forwarding: every player
makes an *outgoing* connection to the same well-known server and subscribes
to a topic named after the room code. No inbound ports, no public IP, and it
works from behind the strictest home router.
"""

from __future__ import annotations

import os
import queue
import threading
from typing import Protocol

from bummsschloss import config
from bummsschloss.net import protocol


class Transport(Protocol):
    """A pipe that carries messages to and from the other players."""

    @property
    def connected(self) -> bool: ...

    @property
    def error(self) -> str | None: ...

    def publish(self, payload: dict) -> None: ...

    def receive(self) -> list[dict]: ...

    def close(self) -> None: ...


class LoopbackBus:
    """An in-process stand-in for a broker, used by the tests.

    Hand out :meth:`connect` transports and every message published on one of
    them turns up on all of them.
    """

    def __init__(self) -> None:
        self._transports: list[LoopbackTransport] = []
        #: Transports in here keep collecting post but stop reading it, which
        #: is how the tests play a peer that has fallen behind.
        self.paused: set[LoopbackTransport] = set()

    def connect(self, name: str = "") -> LoopbackTransport:
        transport = LoopbackTransport(self, name)
        self._transports.append(transport)
        return transport

    def deliver(self, payload: dict) -> None:
        for transport in self._transports:
            if transport.closed:
                continue
            transport.inbox.append(dict(payload))


class LoopbackTransport:
    """One end of a :class:`LoopbackBus`."""

    def __init__(self, bus: LoopbackBus, name: str = "") -> None:
        self.bus = bus
        self.name = name
        self.inbox: list[dict] = []
        self.sent: list[dict] = []
        self.closed = False

    @property
    def connected(self) -> bool:
        return not self.closed

    @property
    def error(self) -> str | None:
        return None

    def publish(self, payload: dict) -> None:
        if self.closed:
            return
        self.sent.append(dict(payload))
        self.bus.deliver(payload)

    def receive(self) -> list[dict]:
        if self in self.bus.paused:
            return []
        messages, self.inbox = self.inbox, []
        return messages

    def close(self) -> None:
        self.closed = True


class MqttTransport:
    """A room on a public MQTT broker.

    The broker is only ever a postbox: it has no idea what the game is, it
    stores nothing, and any of the free public ones will do. All the state
    lives in the players' own copies of the match.

    The connection is made over whatever the address asks for: plain MQTT at
    home, or MQTT inside a TLS WebSocket - which looks exactly like HTTPS -
    where a firewall only lets web traffic out.
    """

    def __init__(
        self,
        room: str,
        *,
        address: str = "",
        client_id: str = "",
        keepalive: int = 30,
    ) -> None:
        import paho.mqtt.client as mqtt

        # Read the address now rather than at import time, so the command line
        # can still redirect the game at a different broker.
        self.address = address or config.MQTT_BROKER
        scheme, host, port, path = config.parse_broker(self.address)

        self.room = room
        self.topic = f"{config.MQTT_TOPIC_PREFIX}/{room}"
        self._inbox: queue.Queue[dict] = queue.Queue()
        self._connected = threading.Event()
        self._error: str | None = None
        self._closed = False

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id or None,
            protocol=mqtt.MQTTv311,
            transport="websockets" if scheme in ("ws", "wss") else "tcp",
        )
        if scheme in ("ws", "wss"):
            self._client.ws_set_options(path=path)
        if scheme == "wss":
            self._client.tls_set()
        self._set_proxy()
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        try:
            self._client.connect_async(host, port, keepalive)
            self._client.loop_start()
        except OSError as exc:  # pragma: no cover - needs a broken network
            self._error = str(exc)

    def _set_proxy(self) -> None:
        """Route through the company proxy if the environment names one."""
        setting = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or ""
        if not setting:
            return
        try:
            import socks
        except ImportError:  # pragma: no cover - PySocks is an extra
            self._error = "a proxy is configured but PySocks is not installed"
            return
        _scheme, host, port, _path = config.parse_broker(setting)
        self._client.proxy_set(proxy_type=socks.HTTP, proxy_addr=host, proxy_port=port or 8080)
    # -- callbacks (these run on paho's own thread) -------------------------

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        if getattr(reason_code, "is_failure", False):
            self._error = str(reason_code)
            return
        self._error = None
        client.subscribe(self.topic, qos=1)
        self._connected.set()

    def _on_disconnect(self, client, userdata, *args) -> None:
        self._connected.clear()
        if not self._closed:
            # paho reconnects by itself; just let the view know meanwhile.
            self._error = "lost the connection to the broker"

    def _on_message(self, client, userdata, message) -> None:
        payload = protocol.decode(message.payload)
        if payload is not None:
            self._inbox.put(payload)

    # -- the Transport side -------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    @property
    def error(self) -> str | None:
        return self._error

    def publish(self, payload: dict) -> None:
        if self._closed:
            return
        self._client.publish(self.topic, protocol.encode(payload), qos=1)

    def receive(self) -> list[dict]:
        messages = []
        while True:
            try:
                messages.append(self._inbox.get_nowait())
            except queue.Empty:
                return messages

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._client.loop_stop()
        try:
            self._client.disconnect()
        except OSError:  # pragma: no cover - already gone
            pass
