"""Command-line entry point for Greenhouses.

The CLI is the public entry point: users run ``greenhouses``. It uses the
standard-library ``argparse`` and adds no argument handling of its own.

The ``run`` subcommand is a thin caller of the runtime service: it builds an
in-memory, offline environment and runs the lifecycle once through the
documented contracts. It contains no flow logic, so a fuller operator workflow
can later be built on the same service.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Never

from greenhouses import __version__
from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.lifecycle import RunRecord
from greenhouses.fakes.local import (
    DEFAULT_AUTOMATION,
    DEFAULT_ITEM_ID,
    LocalEnvironment,
    build_local_environment,
)


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


def _summarize(environment: LocalEnvironment, record: RunRecord) -> dict[str, object]:
    publications = environment.provider.publications
    artifact_id = publications[-1].artifact_id if publications else None
    artifact = environment.artifacts.load(artifact_id) if artifact_id is not None else None
    return {
        "run_id": record.run_id,
        "trigger_id": record.trigger_id,
        "item_id": record.item_id,
        "finalization": None if record.finalization is None else record.finalization.value,
        "states": [state.value for state in record.history],
        "published": bool(publications),
        "artifact_id": artifact_id,
        "artifact": None if artifact is None else json.loads(artifact.to_json()),
    }


def _run(args: argparse.Namespace) -> int:
    """Run one local, offline demonstration of the lifecycle."""
    environment = build_local_environment(
        automation=AutomationId(args.automation),
        item_id=args.item,
    )
    record = environment.dispatcher.deliver(environment.default_event())
    print(json.dumps(_summarize(environment, record), ensure_ascii=False, sort_keys=True))
    return 0


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
    subparsers = parser.add_subparsers(dest="command")
    run_parser = subparsers.add_parser(
        "run",
        help="run one local, offline demonstration of the lifecycle",
        description="Run the eleven-step lifecycle once against in-memory, offline fakes.",
        formatter_class=_HelpFormatter,
    )
    run_parser.add_argument(
        "--automation",
        default=DEFAULT_AUTOMATION.name,
        help="the automation identity to run (default: %(default)s)",
    )
    run_parser.add_argument(
        "--item",
        default=DEFAULT_ITEM_ID,
        help="the work item to act on (default: %(default)s)",
    )
    run_parser.set_defaults(handler=_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return its exit status without terminating the caller."""
    args = sys.argv[1:] if argv is None else list(argv)
    parser = _build_parser()
    try:
        parsed = parser.parse_args(args)
    except _ParserExit as exc:
        return exc.status
    handler = getattr(parsed, "handler", None)
    if not args or handler is None:
        parser.print_help()
        return 0
    return int(handler(parsed))
