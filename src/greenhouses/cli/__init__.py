"""Command-line entry point for Greenhouses.

The CLI is the public entry point: users run ``greenhouses``. It uses the
standard-library ``argparse`` and adds no argument handling of its own.
"""

from __future__ import annotations

import argparse
import sys
from typing import Never

from greenhouses import __version__


class _HelpFormatter(argparse.HelpFormatter):
    """Help formatter with a fixed width.

    ``argparse``'s default formatter asks the terminal for its size, which reads
    the ``COLUMNS`` and ``LINES`` environment variables. The CLI must read none
    of those, so the width is fixed here.
    """

    def __init__(self, prog: str) -> None:
        super().__init__(prog, width=80)


class _ParserExit(Exception):
    """Status ``argparse`` would have exited with, returned to the caller instead."""

    def __init__(self, status: int) -> None:
        super().__init__(status)
        self.status = status


class _Parser(argparse.ArgumentParser):
    """``argparse`` terminates the interpreter on help, version and errors.

    ``main()`` returns that status instead of letting the interpreter exit, so
    the exit is turned into an exception that never leaves the CLI.
    """

    def exit(self, status: int = 0, message: str | None = None) -> Never:
        if message:
            sys.stderr.write(message)
        raise _ParserExit(status)

    def error(self, message: str) -> Never:
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
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
    try:
        parser.parse_args(args)
    except _ParserExit as exc:
        return exc.status
    if not args:
        parser.print_help()
    return 0
