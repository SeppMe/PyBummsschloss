"""Entry point:  ``python -m ballerburg``  or the ``ballerburg`` command."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from ballerburg import __version__, config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ballerburg", description=config.GAME_TITLE)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--scene",
        default="demo",
        choices=["demo"],
        help="which scene to start in (default: %(default)s)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Imported late so that --help/--version do not pay for initialising SDL.
    from ballerburg.app import App
    from ballerburg.scenes.demo import DemoScene

    scenes = {"demo": DemoScene}
    app = App()
    app.run(scenes[args.scene](app))
    return 0


if __name__ == "__main__":
    sys.exit(main())
