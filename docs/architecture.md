# Architecture

Status: partial. This architecture grows with the issues that implement each layer.

## Current package structure

```
src/greenhouses/
├── __init__.py            # __version__
├── cli/__init__.py        # argparse entry point: greenhouses
└── core/
    ├── __init__.py
    └── domain/
        ├── __init__.py
        └── revision.py    # compute_revision
```

Tests live under `tests/`, with negative fixtures under `tests/fixtures/` that the import
boundary check is pointed at.

## Intended dependency direction

Dependencies point inwards, towards `core`, which depends on nothing but the standard library
and other `core` modules:

- `core` contains domain logic. It does not access the environment or the filesystem, and it
  does not import `runtime`, `roles`, `cli`, `profiles`, any provider or infrastructure.
- `cli` is the public entry point. Users run `greenhouses`, never `python` or `uv run`.
- The future `runtime`, `roles` and `profiles` sit outside core. Only the CLI and profiles
  resolve user configuration from environment variables and configuration files. Runtime
  operations may access the filesystem and external systems through explicit interfaces. A
  role never publishes; publication is a runtime operation.

## Implemented and planned

Implemented in this repository:

- The `greenhouses` package at version 0.1.0 and its installable `greenhouses` command with
  `--version`, `--help` and no-argument usage.
- The `compute_revision` domain function, the only place a revision is computed.
- Clone-based maintainer installation through `install.sh`.

Planned, not implemented:

- A runtime for supervised automations (execution in isolation, then validation and external
  effects through a trusted supervisor), with the software factory as its first catalogue entry.
- `roles`, `profiles`, ports, persistence, artifacts and provider integrations.

## Installation

Installation from a clone only. The installed command points at the checkout; network
installation and tagged releases come with the first tag.
