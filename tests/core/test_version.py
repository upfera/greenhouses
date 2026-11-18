"""The package version must match the installed distribution metadata."""

from __future__ import annotations

import importlib.metadata

import greenhouses


def test_version_matches_installed_metadata() -> None:
    # Must fail, not skip, when metadata is missing: a missing install is a broken setup.
    installed = importlib.metadata.version("greenhouses")  # raises PackageNotFoundError
    assert greenhouses.__version__ == installed
