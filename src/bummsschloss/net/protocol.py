"""What the players say to each other.

Messages are plain JSON dictionaries with a ``type`` and a ``from`` field.
Everyone in a room sees everything - including their own messages, because
the broker echoes them back - so the rules below are written as "whoever is
allowed to send this".

===========  ======  ===================================================
Message      Sender  Meaning
===========  ======  ===================================================
``hello``    anyone  I am here, this is my name
``lobby``    host    the current seating, resent whenever it changes
``start``    host    the match begins, here is the opening position
``turn``     active  my aim and my weapon; everybody fire
``sync``     host    after turn N the world looked like this (hash)
``resync``   guest   my world looks different, please send me yours
``state``    host    here is my world, overwrite yours with it
``bye``      anyone  I am leaving
===========  ======  ===================================================

A room code is short and spoken out loud, so it uses an alphabet without the
characters people confuse (no O/0, no I/1).
"""

from __future__ import annotations

import json
import random
import string

#: Bumped whenever the message format changes; peers refuse to mix versions.
PROTOCOL_VERSION = 1

#: Characters a room code is made of.
ROOM_ALPHABET = "".join(c for c in string.ascii_uppercase + string.digits if c not in "O0I1")
ROOM_CODE_LENGTH = 5

HELLO = "hello"
LOBBY = "lobby"
START = "start"
TURN = "turn"
SYNC = "sync"
RESYNC = "resync"
STATE = "state"
BYE = "bye"


def new_room_code(rng: random.Random | None = None) -> str:
    """A short code the players can read out to each other."""
    rng = rng or random.SystemRandom()
    return "".join(rng.choice(ROOM_ALPHABET) for _ in range(ROOM_CODE_LENGTH))


def clean_room_code(text: str) -> str:
    """Normalise what somebody typed into a room code."""
    return "".join(c for c in text.upper() if c in ROOM_ALPHABET)[:ROOM_CODE_LENGTH]


def message(kind: str, sender: str, **fields) -> dict:
    """Build a message ready for :func:`encode`."""
    return {"v": PROTOCOL_VERSION, "type": kind, "from": sender, **fields}


def encode(payload: dict) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def decode(raw: bytes) -> dict | None:
    """Parse a message, or return ``None`` if it is not one of ours."""
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("v") != PROTOCOL_VERSION or "type" not in payload:
        return None
    return payload
