# Greenhouses

Greenhouses is a vendor-neutral platform for two-phase automations: an untrusted execution
phase, in which an agent or a deterministic step produces a structured result, and a trusted
finalization phase, which checks that result against the current state and performs any
external effect. The software factory is planned as the first catalogue of such automations,
and other automations such as digests, monitors or reports are expected to reuse the same
runtime. This repository currently contains only the package skeleton, the installable
`greenhouses` command and the `compute_revision` domain function.

## Prerequisites

- `uv` 0.13.0 or newer on `PATH`.
- The uv tool binary directory on `PATH`. Print it with:

  ```sh
  uv tool dir --bin
  ```

## Installation

Install from a clone:

```sh
./install.sh
```

The installed command points at this checkout (an editable install). Moving or removing the
repository breaks it; run `./install.sh` again from the new location.

## Usage

```sh
greenhouses --version
greenhouses --help
```

## Development

```sh
uv sync --locked --group test --no-build
uv run --locked --group test --no-build ruff check .
uv run --locked --group test --no-build ruff format --check .
uv run --locked --group test --no-build mypy src
uv run --locked --group test --no-build pytest --cov --cov-report=xml
```

Tests run only via `uv run --locked --group test --no-build pytest`. Running `pytest` outside `uv run`
is not supported.

See [`AGENTS.md`](AGENTS.md) for the engineering and architecture rules, and
[`docs/architecture.md`](docs/architecture.md) for the current and planned structure.
