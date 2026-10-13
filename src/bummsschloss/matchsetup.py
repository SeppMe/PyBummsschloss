"""The choices made before a match starts.

:class:`MatchSetup` is the hand-over point between the pre-match menu and the
rules engine: the menu edits one of these, :class:`~bummsschloss.match.Match`
consumes it. It deliberately knows nothing about pygame, so the same object can
later be sent over the wire to set up a network game.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from bummsschloss import config

#: Default seat names, used until a player types something else.
DEFAULT_NAMES: tuple[str, ...] = ("Player 1", "Player 2", "Player 3", "Player 4")

#: Longest name the menu accepts, so HUD panels cannot overflow.
MAX_NAME_LENGTH = 14


class IncomeModel(Enum):
    """How the lump sum handed out at the start of a turn is worked out."""

    FLAT = "flat"
    RISING = "rising"
    CATCHUP = "catchup"

    @property
    def label(self) -> str:
        """Short, translatable name for the menu."""
        return _MODEL_TEXT[self][0]

    @property
    def description(self) -> str:
        """One-line explanation, translatable."""
        return _MODEL_TEXT[self][1]


_MODEL_TEXT: dict[IncomeModel, tuple[str, str]] = {
    IncomeModel.FLAT: (
        "flat",
        "Everybody gets the same amount every turn.",
    ),
    IncomeModel.RISING: (
        "rising",
        "The income grows with every round, so later weapons get affordable.",
    ),
    IncomeModel.CATCHUP: (
        "catch-up",
        "The worse your castle looks, the more you are paid.",
    ),
}


@dataclass
class PlayerSetup:
    """One configured seat."""

    name: str
    color_index: int

    @property
    def color(self) -> config.Color:
        return config.player_color(self.color_index)


@dataclass
class MatchSetup:
    """Everything the menu lets the players decide."""

    players: list[PlayerSetup] = field(default_factory=list)
    starting_money: int = config.STARTING_MONEY
    turn_income: int = config.TURN_INCOME
    income_model: IncomeModel = IncomeModel.FLAT
    #: ``None`` means "roll a fresh landscape".
    seed: int | None = None

    def __post_init__(self) -> None:
        if not self.players:
            self.set_player_count(config.MIN_PLAYERS)

    # -- seats --------------------------------------------------------------

    @classmethod
    def default(cls, player_count: int = config.MIN_PLAYERS, **kwargs) -> MatchSetup:
        setup = cls(**kwargs)
        setup.set_player_count(player_count)
        return setup

    @property
    def player_count(self) -> int:
        return len(self.players)

    def set_player_count(self, count: int) -> None:
        """Grow or shrink the table, keeping the seats that are already there."""
        count = max(config.MIN_PLAYERS, min(config.MAX_PLAYERS, count))
        while len(self.players) > count:
            self.players.pop()
        while len(self.players) < count:
            index = len(self.players)
            self.players.append(
                PlayerSetup(name=DEFAULT_NAMES[index], color_index=self._free_color())
            )

    def _free_color(self) -> int:
        """Pick the first palette entry nobody has claimed yet."""
        taken = {player.color_index for player in self.players}
        for index in range(len(config.PLAYER_PALETTE)):
            if index not in taken:
                return index
        return len(self.players) % len(config.PLAYER_PALETTE)

    # -- editing ------------------------------------------------------------

    def rename(self, seat: int, name: str) -> None:
        self.players[seat].name = name[:MAX_NAME_LENGTH]

    def is_default_name(self, seat: int) -> bool:
        """True while a seat still carries the untouched default name."""
        return self.players[seat].name == DEFAULT_NAMES[seat]

    def display_name(self, seat: int) -> str:
        """The name to show; falls back to the default when the field is empty."""
        name = self.players[seat].name.strip()
        return name or DEFAULT_NAMES[seat]

    def cycle_color(self, seat: int, step: int = 1) -> None:
        """Move a seat to the next free colour, so two seats never clash."""
        size = len(config.PLAYER_PALETTE)
        taken = {p.color_index for i, p in enumerate(self.players) if i != seat}
        current = self.players[seat].color_index
        for offset in range(1, size + 1):
            candidate = (current + step * offset) % size
            if candidate not in taken:
                self.players[seat].color_index = candidate
                return

    def cycle_starting_money(self, step: int = 1) -> None:
        self.starting_money = _cycle(config.STARTING_MONEY_CHOICES, self.starting_money, step)

    def cycle_turn_income(self, step: int = 1) -> None:
        self.turn_income = _cycle(config.TURN_INCOME_CHOICES, self.turn_income, step)

    def cycle_income_model(self, step: int = 1) -> None:
        models = list(IncomeModel)
        index = models.index(self.income_model)
        self.income_model = models[(index + step) % len(models)]

    # -- economy ------------------------------------------------------------

    def income_for(self, *, round_number: int, health_fraction: float) -> int:
        """Work out one turn's lump sum for a player.

        ``round_number`` counts full rounds from 1, ``health_fraction`` is the
        player's remaining castle health between 0 and 1.
        """
        amount = float(self.turn_income)
        if self.income_model is IncomeModel.RISING:
            amount *= 1.0 + config.INCOME_RISE_PER_ROUND * max(0, round_number - 1)
        elif self.income_model is IncomeModel.CATCHUP:
            missing = max(0.0, min(1.0, 1.0 - health_fraction))
            amount *= 1.0 + config.INCOME_CATCHUP_BONUS * missing
        return int(round(amount))

    # -- going over the wire ------------------------------------------------

    def to_dict(self) -> dict:
        """A plain-data copy, ready to be sent to the other players."""
        return {
            "players": [
                {"name": seat.name, "color_index": seat.color_index} for seat in self.players
            ],
            "starting_money": self.starting_money,
            "turn_income": self.turn_income,
            "income_model": self.income_model.value,
            "seed": self.seed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MatchSetup:
        setup = cls(
            players=[
                PlayerSetup(name=seat["name"], color_index=seat["color_index"])
                for seat in data["players"]
            ],
            starting_money=data["starting_money"],
            turn_income=data["turn_income"],
            income_model=IncomeModel(data["income_model"]),
            seed=data.get("seed"),
        )
        return setup


def _cycle(choices: tuple[int, ...], current: int, step: int) -> int:
    """Step through a list of offered values, landing on the nearest on a miss."""
    if current in choices:
        index = choices.index(current)
    else:
        index = min(range(len(choices)), key=lambda i: abs(choices[i] - current))
    return choices[(index + step) % len(choices)]