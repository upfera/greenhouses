"""Behaviour of the maintainer installer.

The installer is exercised as a subprocess with a fake ``uv`` on a controlled
``PATH``. No network access and no real ``uv`` are involved.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL = REPO_ROOT / "install.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(stat.S_IRWXU)


def _fake_uv(
    bin_dir: Path, tool_bin: Path, log: Path, version: str = "0.13.9", install_status: int = 0
) -> None:
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
        f"    exit {install_status}\n"
        "fi\n"
        "exit 0\n",
    )


def _fake_greenhouses(bin_dir: Path, log: Path | None = None, version: str = "0.1.0") -> None:
    body = f"echo {version}\n"
    if log is not None:
        body = f'echo "$@" >> "{log}"\n' + body
    _write_executable(bin_dir / "greenhouses", "#!/bin/sh\n" + body)


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


def _installer(
    tmp_path: Path,
    version: str = "0.13.9",
    install_status: int = 0,
    *,
    args: list[str] | None = None,
    extra_path: tuple[Path, ...] = (),
) -> tuple[subprocess.CompletedProcess[str], str, str]:
    """Run the installer against a fake `uv` reporting `version`.

    Returns the completed process, the `uv` log and the log of the fake `greenhouses`.
    """
    bin_dir, tool_bin = tmp_path / "bin", tmp_path / "tools"
    bin_dir.mkdir()
    tool_bin.mkdir()
    uv_log = tmp_path / "uv.log"
    cli_log = tmp_path / "greenhouses.log"
    _fake_uv(bin_dir, tool_bin, uv_log, version=version, install_status=install_status)
    _fake_greenhouses(tool_bin, log=cli_log)
    result = _run(args or [], [*extra_path, bin_dir, tool_bin])

    def read(path: Path) -> str:
        return path.read_text(encoding="utf-8") if path.exists() else ""

    return result, read(uv_log), read(cli_log)


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


@pytest.mark.parametrize(
    ("version", "status"),
    [
        ("0.12.99", 1),  # below the floor
        ("0.13.0rc1", 1),  # a release candidate is not a stable release
        ("0.14.0-dev.1", 1),  # nor is a development build, however new it is
        ("0.13.0", 0),  # the floor itself
        ("0.13.9", 0),  # a stable release above the floor
        ("0.13.0+build5", 0),  # build metadata is not a pre-release
    ],
)
def test_the_uv_version_policy(tmp_path: Path, version: str, status: int) -> None:
    result, uv_log, _ = _installer(tmp_path, version=version)

    assert result.returncode == status
    if status == 1:
        assert "0.13.0" in result.stderr
        # The policy is checked before any other `uv` command runs.
        assert uv_log.strip() == "--version"


def test_unreadable_uv_version_exits_one(tmp_path: Path) -> None:
    result, uv_log, _ = _installer(tmp_path, version="unknown")

    assert result.returncode == 1
    assert "uv --version" in result.stderr
    assert "tool install" not in uv_log


def test_missing_tool_bin_dir_exits_one_before_install(tmp_path: Path) -> None:
    bin_dir, tool_bin = tmp_path / "bin", tmp_path / "tools"
    bin_dir.mkdir()
    tool_bin.mkdir()
    log = tmp_path / "uv.log"
    _fake_uv(bin_dir, tool_bin, log)

    result = _run([], [bin_dir])

    assert result.returncode == 1
    assert f'export PATH="{tool_bin}:$PATH"' in result.stderr
    assert not log.exists() or "tool install" not in log.read_text(encoding="utf-8")


def test_successful_install(tmp_path: Path) -> None:
    result, uv_log, _ = _installer(tmp_path)

    assert result.returncode == 0
    assert "tool install --editable --force --no-build ." in uv_log
    assert "0.1.0" in result.stdout


def test_greenhouses_is_run_with_version(tmp_path: Path) -> None:
    result, _, cli_log = _installer(tmp_path)

    assert result.returncode == 0
    assert cli_log.strip() == "--version"


def test_an_earlier_greenhouses_on_path_is_not_the_one_verified(tmp_path: Path) -> None:
    # A stale `greenhouses` earlier on PATH must not be what the installer verifies.
    earlier = tmp_path / "earlier"
    earlier.mkdir()
    _fake_greenhouses(earlier, version="9.9.9")

    result, _, _ = _installer(tmp_path, extra_path=(earlier,))

    assert result.returncode == 0
    assert "0.1.0" in result.stdout
    assert "9.9.9" not in result.stdout


def test_a_failing_install_is_reported(tmp_path: Path) -> None:
    result, _, _ = _installer(tmp_path, install_status=1)

    assert result.returncode != 0
    assert "0.1.0" not in result.stdout
