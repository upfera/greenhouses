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

# Parsed with parameter expansion only: the tests run this script on a minimal PATH.
# The suffix is stripped, not judged: uv has never published a pre-release, and a newer
# build carrying one (0.14.0-dev.1) must not be refused.
uv_version=$(uv --version)
uv_version=${uv_version#* }
uv_version=${uv_version%% *}
uv_major=${uv_version%%.*}
uv_rest=${uv_version#*.}
uv_minor=${uv_rest%%.*}
uv_major=${uv_major%%[!0-9]*}
uv_minor=${uv_minor%%[!0-9]*}

if [ -z "$uv_major" ] || [ -z "$uv_minor" ]; then
    echo "error: could not read the uv version from 'uv --version'." >&2
    exit 1
fi

if [ "$uv_major" -eq 0 ] && [ "$uv_minor" -lt 13 ]; then
    echo "error: uv $uv_version is too old; 0.13.0 or newer is required." >&2
    echo "Below 0.13.0, '--no-build' also blocks building this project from source." >&2
    echo "Update uv from https://docs.astral.sh/uv/ and run this script again." >&2
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
