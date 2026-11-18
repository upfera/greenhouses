"""CLI contract: return codes, streams and environment access."""

from __future__ import annotations

import builtins
import os
from typing import Any

from greenhouses.cli import main

# The keys the standard library's translation lookup consults.
LOCALE_KEYS = ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")


class _RecordingEnviron(dict[str, str]):
    """An ``os.environ`` stand-in that records and restricts key access."""

    def __init__(self, data: dict[str, str], accessed: set[str], allowed: tuple[str, ...]) -> None:
        super().__init__(data)
        self._accessed = accessed
        self._allowed = allowed

    def __getitem__(self, key: str) -> str:
        self._accessed.add(key)
        if key not in self._allowed:
            raise AssertionError(f"unexpected environment access: {key!r}")
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        self._accessed.add(key)
        if key not in self._allowed:
            raise AssertionError(f"unexpected environment access: {key!r}")
        return super().get(key, default)


def test_version_prints_to_stdout(capsys: Any) -> None:
    assert main(["--version"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "0.1.0\n"
    assert captured.err == ""


def test_help_prints_usage_to_stdout(capsys: Any) -> None:
    assert main(["--help"]) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("usage: greenhouses")
    assert captured.err == ""


def test_no_arguments_prints_usage_to_stdout(capsys: Any) -> None:
    assert main([]) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("usage: greenhouses")
    assert captured.err == ""


def test_unknown_argument_writes_diagnostic_to_stderr(capsys: Any) -> None:
    assert main(["--unknown"]) == 2
    captured = capsys.readouterr()
    assert captured.err != ""
    assert captured.out == ""


def test_help_reads_only_locale_variables_and_no_files(monkeypatch: Any, capsys: Any) -> None:
    # ``--help`` performs the standard locale lookup through gettext. That lookup
    # reads only these variables; no other environment access and no file open is
    # allowed on the real code path. gettext is deliberately not stubbed.
    accessed: set[str] = set()
    recording = _RecordingEnviron(dict(os.environ), accessed, LOCALE_KEYS)
    monkeypatch.setattr(os, "environ", recording)

    opened: list[tuple[Any, ...]] = []
    real_open = builtins.open

    def recording_open(*args: Any, **kwargs: Any) -> Any:
        opened.append(args)
        return real_open(*args, **kwargs)

    with monkeypatch.context() as patched:
        patched.setattr(builtins, "open", recording_open)
        assert main(["--help"]) == 0

    captured = capsys.readouterr()
    assert captured.out.startswith("usage: greenhouses")
    assert opened == []
    assert accessed, "the locale lookup must run on --help"
    assert accessed <= set(LOCALE_KEYS)
    assert "LANGUAGE" in accessed
