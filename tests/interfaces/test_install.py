"""Behaviour of the maintainer installer.

The installer is exercised as a subprocess with a fake ``uv`` on a controlled
``PATH``. No network access and no real ``uv`` are involved.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL = REPO_ROOT / "install.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(stat.S_IRWXU)


def _fake_uv(bin_dir: Path, tool_bin: Path, log: Path, version: str = "0.13.9") -> None:
    _write_executable(
        bin_dir / "uv",
        "#!/bin/sh\n"
        f'echo "$@" >> "{log}"\n'
        'if [ "$1" = "--version" ]; then\n'
        f'    echo "uv {version}"\n'
        "    exit 0\n"
        "fi\n"
        'if [ "$1" = "tool" ] && [ "$2" = "dir" ] && [ "$3" = "--bin" ]; then\n'
        f'    echo "{tool_bin}"\n'
        "    exit 0\n"
        "fi\n"
        'if [ "$1" = "tool" ] && [ "$2" = "install" ]; then\n'
        "    exit 0\n"
        "fi\n"
        "exit 0\n",
    )


def _fake_greenhouses(bin_dir: Path) -> None:
    _write_executable(bin_dir / "greenhouses", "#!/bin/sh\necho 0.1.0\n")


def _run(args: list[str], path_dirs: list[Path]) -> subprocess.CompletedProcess[str]:
    env = {"PATH": os.pathsep.join(str(directory) for directory in path_dirs)}
    return subprocess.run(
        ["./install.sh", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_help_exits_zero(tmp_path: Path) -> None:
    result = _run(["--help"], [])
    assert result.returncode == 0
    assert "Usage" in result.stdout


def test_unknown_argument_exits_two(tmp_path: Path) -> None:
    result = _run(["bogus"], [])
    assert result.returncode == 2
    assert result.stderr != ""


def test_missing_uv_exits_one_without_running_uv(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    log = tmp_path / "uv.log"

    result = _run([], [empty])

    assert result.returncode == 1
    assert "uv" in result.stderr
    assert not log.exists()


def test_old_uv_exits_one_with_the_required_version(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tool_bin = tmp_path / "tools"
    tool_bin.mkdir()
    log = tmp_path / "uv.log"
    _fake_uv(bin_dir, tool_bin, log, version="0.12.0")
    _fake_greenhouses(tool_bin)

    result = _run([], [bin_dir, tool_bin])

    assert result.returncode == 1
    assert "0.13.0" in result.stderr
    assert "tool install" not in log.read_text(encoding="utf-8")


def test_top_of_the_old_band_is_rejected(tmp_path: Path) -> None:
    # 0.12.99, not 0.12.0: the guard compares major and minor only, so the highest
    # release below the boundary is the one that would expose an off-by-one.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tool_bin = tmp_path / "tools"
    tool_bin.mkdir()
    log = tmp_path / "uv.log"
    _fake_uv(bin_dir, tool_bin, log, version="0.12.99")
    _fake_greenhouses(tool_bin)

    result = _run([], [bin_dir, tool_bin])

    assert result.returncode == 1
    assert "0.13.0" in result.stderr
    assert "tool install" not in log.read_text(encoding="utf-8")


def test_pre_release_uv_version_does_not_abort_the_check(tmp_path: Path) -> None:
    # Robustness, not policy: uv has never published a pre-release, so the suffix is
    # stripped rather than judged. Judging it would also refuse a newer build that
    # carries one (0.14.0-dev.1), which works.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tool_bin = tmp_path / "tools"
    tool_bin.mkdir()
    log = tmp_path / "uv.log"
    _fake_uv(bin_dir, tool_bin, log, version="0.13.0rc1")
    _fake_greenhouses(tool_bin)

    result = _run([], [bin_dir, tool_bin])

    assert result.returncode == 0


def test_unreadable_uv_version_exits_one(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tool_bin = tmp_path / "tools"
    tool_bin.mkdir()
    log = tmp_path / "uv.log"
    _fake_uv(bin_dir, tool_bin, log, version="unknown")
    _fake_greenhouses(tool_bin)

    result = _run([], [bin_dir, tool_bin])

    assert result.returncode == 1
    assert "uv --version" in result.stderr
    assert "tool install" not in log.read_text(encoding="utf-8")


def test_missing_tool_bin_dir_exits_one_before_install(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tool_bin = tmp_path / "tools"
    tool_bin.mkdir()
    log = tmp_path / "uv.log"
    _fake_uv(bin_dir, tool_bin, log)

    result = _run([], [bin_dir])

    assert result.returncode == 1
    assert f'export PATH="{tool_bin}:$PATH"' in result.stderr
    assert not log.exists() or "tool install" not in log.read_text(encoding="utf-8")


def test_successful_install(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tool_bin = tmp_path / "tools"
    tool_bin.mkdir()
    log = tmp_path / "uv.log"
    _fake_uv(bin_dir, tool_bin, log)
    _fake_greenhouses(tool_bin)

    result = _run([], [bin_dir, tool_bin])

    assert result.returncode == 0
    assert "tool install --editable --force --no-build ." in log.read_text(encoding="utf-8")
    assert "0.1.0" in result.stdout
