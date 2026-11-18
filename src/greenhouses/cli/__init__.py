"""Command-line entry point for Greenhouses.

The CLI is the public entry point: users run ``greenhouses``. It uses the
standard-library ``argparse`` and adds no argument handling of its own.
"""

from __future__ import annotations

import argparse
import sys

from greenhouses import __version__


class _HelpFormatter(argparse.HelpFormatter):
    """Help formatter with a fixed width.

    ``argparse``'s default formatter asks the terminal for its size, which reads
    the ``COLUMNS`` and ``LINES`` environment variables. The CLI must read none
    of those, so the width is fixed here.
    """

    def __init__(self, prog: str) -> None:
        super().__init__(prog, width=80)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="greenhouses",
        formatter_class=_HelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return its exit status without terminating the caller."""
    args = sys.argv[1:] if argv is None else list(argv)
    parser = _build_parser()
    if not args:
        parser.print_help()
        return 0
    try:
        parser.parse_args(args)
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 0
    return 0
