# AGENTS.md

Instructions for AI coding agents and automation working in this repository. Humans: see the
organization's [CONTRIBUTING.md](https://github.com/upfera/.github/blob/main/CONTRIBUTING.md).

## Workflow

- Work from an issue. Branch from `main`; never commit directly to `main`.
- One focused change per pull request, linked with `Closes #N`.
- Pull request titles and commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).
- Pull requests are squash-merged; the PR title becomes the commit message.

## Commits

- Commits are signed and authored by the configured git identity. Do not change `user.name` or `user.email`.
- Do not add `Co-authored-by` or `Signed-off-by` trailers, or any other attribution lines.

## Quality

- Run the project's build, tests, and linters before opening a pull request, and say what you ran in the PR.
- Update documentation together with the code it describes.
- Never commit secrets or credentials. Local configuration belongs in `.env` (ignored); document variables in `.env.example`.

## Project commands

- Build: `uv sync --locked --group test --no-build`
- Test: `uv run --locked --group test --no-build pytest`
- Lint/format: `uv run --locked --group test --no-build ruff check .` and `uv run --locked --group test --no-build ruff format --check .`
- Types: `uv run --locked --group test --no-build mypy src`

Tests run only via `uv run --locked --group test --no-build pytest`; running `pytest` outside `uv run` is
not supported.

## Architecture

- `core/` contains domain logic and depends on nothing in `runtime/`, `roles/`, `cli/`,
  `profiles/`, any provider or infrastructure.
- Core domain logic does not access the environment or the filesystem.
- Only the CLI and profiles resolve user configuration from environment variables and
  configuration files. The CLI's only other environment access is the standard locale lookup
  for messages.
- Runtime operations may access the filesystem and external systems through explicit
  interfaces.
- A role never publishes. Publication is a runtime operation.
- New ports and modules come with a real call site in a test or flow, never speculatively.
- A revision is computed only by `compute_revision`.
- Core names stay generic. Domain concepts are named for their role in a two-phase automation
  (`WorkItem`, `Revision`, `Artifact`, `Finalization`), never for one catalogue entry. GitHub,
  Jira, issue, pull request and factory-role names live in adapters or catalogue code, not in
  `core/`.
- Provider-specific behaviour does not leak into core.
- The CLI is the public entry point. Users run `greenhouses`, never `python` or `uv run`.
- Rules are short and, where a test exists, enforced by it.
- Longer agent-facing material lives in [`.ai/`](.ai/).
