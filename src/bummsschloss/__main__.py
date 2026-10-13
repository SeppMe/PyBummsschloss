"""Entry point:  ``python -m bummsschloss``  or the ``bummsschloss`` command."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from bummsschloss import __version__, config
from bummsschloss.i18n import AVAILABLE_LANGUAGES, detect_language, set_language
from bummsschloss.i18n import gettext as _


def build_parser(default_language: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bummsschloss", description=config.GAME_TITLE)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--scene",
        default="setup",
        choices=["setup", "match", "demo"],
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
        "--lang",
        default=default_language,
        choices=list(AVAILABLE_LANGUAGES),
        help=_("language of the user interface (default: %(default)s)"),
    )
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

    # Imported late so that --help/--version do not pay for initialising SDL.
    from bummsschloss.app import App
    from bummsschloss.match import Match
    from bummsschloss.matchsetup import MatchSetup
    from bummsschloss.scenes.demo import DemoScene
    from bummsschloss.scenes.match import MatchScene
    from bummsschloss.scenes.setup import SetupScene

    setup = MatchSetup.default(args.players, seed=args.seed)
    app = App()
    if args.scene == "demo":
        scene = DemoScene(app)
    elif args.scene == "match":
        scene = MatchScene(app, Match(setup=setup, seed=args.seed))
    else:
        scene = SetupScene(app, setup)
    app.run(scene)
    return 0


if __name__ == "__main__":
    sys.exit(main())
