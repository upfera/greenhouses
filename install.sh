#!/bin/sh
# Maintainer installer: installs the CLI from this checkout, editable, with uv.
set -eu

case "$0" in
    */*) script_dir=${0%/*} ;;
    *) script_dir=. ;;
esac
repository_root=$(CDPATH= cd -- "$script_dir" && pwd)
cd "$repository_root"

usage() {
    echo "Usage: ./install.sh [--help]"
}

if [ "$#" -eq 0 ]; then
    :
elif [ "$#" -eq 1 ] && [ "$1" = "--help" ]; then
    usage
    exit 0
else
    usage >&2
    exit 2
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "error: uv was not found on PATH." >&2
    echo "Install uv from https://docs.astral.sh/uv/ and run this script again." >&2
    exit 1
fi

tool_bin_dir=$(uv tool dir --bin)

case ":${PATH-}:" in
    *":$tool_bin_dir:"*) ;;
    *)
        echo "error: the uv tool binary directory is not on PATH:" >&2
        echo "  $tool_bin_dir" >&2
        echo "Add this line to your shell configuration and open a new shell:" >&2
        echo "export PATH=\"$tool_bin_dir:\$PATH\"" >&2
        exit 1
        ;;
esac

uv tool install --editable --force --no-build .
greenhouses --version
