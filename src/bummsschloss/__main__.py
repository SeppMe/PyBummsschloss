"""Entry point:  ``python -m bummsschloss``  or the ``bummsschloss`` command."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from bummsschloss import __version__, config
from bummsschloss.i18n import AVAILABLE_LANGUAGES, detect_language, set_language
from bummsschloss.i18n import gettext as _


def build_parser(default_language: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bummsschloss", description=config.GAME_TITLE)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--scene",
        default="setup",
        choices=["setup", "match"],
        help=_("which scene to start in (default: %(default)s)"),
    )
    parser.add_argument(
        "--players",
        type=int,
        default=config.MIN_PLAYERS,
        choices=range(config.MIN_PLAYERS, config.MAX_PLAYERS + 1),
        help=_("number of players to preselect in the menu (default: %(default)s)"),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help=_("seed for the random landscape, for reproducible matches"),
    )
    parser.add_argument(
        "--broker",
        default=config.MQTT_BROKER,
        help=_("message broker for network games (default: %(default)s)"),
    )
    parser.add_argument(
        "--lang",
        default=default_language,
        choices=list(AVAILABLE_LANGUAGES),
        help=_("language of the user interface (default: %(default)s)"),
    )
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help=_("check whether this machine can run the game, and report what cannot"),
    )
    # Used by --diagnose to re-invoke itself for a single probe in a child
    # process, so that a crash can be attributed instead of just killing us.
    parser.add_argument("--probe", default=None, help=argparse.SUPPRESS)
    return parser


def preparse_language(argv: Sequence[str] | None) -> str:
    """Resolve the language before argparse runs, so ``--help`` is translated too."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    for i, argument in enumerate(arguments):
        if argument == "--lang" and i + 1 < len(arguments):
            return set_language(arguments[i + 1])
        if argument.startswith("--lang="):
            return set_language(argument.partition("=")[2])
    return set_language(detect_language())


def main(argv: Sequence[str] | None = None) -> int:
    language = preparse_language(argv)
    args = build_parser(language).parse_args(argv)
    set_language(args.lang)
    config.MQTT_BROKER = args.broker

    # The frozen build ships a second, console-attached executable whose only
    # job is the machine check; it is the same program under another name.
    named_diagnose = Path(sys.argv[0]).stem.lower().endswith("diagnose")

    if args.diagnose or named_diagnose:
        # Imported late, like everything else that may touch SDL.
        from bummsschloss import diagnostics

        if args.probe:
            return diagnostics.run_probe(args.probe)
        return diagnostics.run_report()

    # Imported late so that --help/--version do not pay for initialising SDL.
    from bummsschloss.app import App
    from bummsschloss.match import Match
    from bummsschloss.matchsetup import MatchSetup
    from bummsschloss.scenes.match import MatchScene
    from bummsschloss.scenes.setup import SetupScene

    setup = MatchSetup.default(args.players, seed=args.seed)
    app = App()
    if args.scene == "match":
        # Straight into a hotseat match, skipping the menu.
        scene = MatchScene(app, Match(setup=setup, seed=args.seed))
    else:
        scene = SetupScene(app, setup)
    app.run(scene)
    return 0


if __name__ == "__main__":
    sys.exit(main())
