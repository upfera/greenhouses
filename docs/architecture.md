# Architecture

Status: the core foundation is implemented. The eleven-step lifecycle runs end to end over
in-memory ports, and the contracts, ports and boundaries below are enforced by tests. Later
layers (real adapters, manifests, the full operator workflow) grow on top of this.

## Package structure

```
src/greenhouses/
├── __init__.py            # __version__
├── cli/__init__.py        # argparse entry point: greenhouses (incl. the run subcommand)
├── core/
│   ├── domain/            # domain types, the state machine, the artifact contract
│   │   ├── errors.py          # domain errors, none carrying a secret value
│   │   ├── identity.py        # AutomationId
│   │   ├── work_item.py       # WorkItem, Revision
│   │   ├── trigger.py         # Trigger, TriggerSource (the normalized trigger)
│   │   ├── configuration.py   # Configuration, ExecutionPolicy
│   │   ├── secrets.py         # scopes, refs, grants, GrantedSecrets, SecretValue
│   │   ├── execution.py       # InputSnapshot, ExecutionRequest, ExecutionState, ExecutionOutput
│   │   ├── artifact.py        # Artifact (versioned, serializable, vendor-neutral)
│   │   ├── publication.py     # Publication, PublicationReceipt
│   │   ├── lifecycle.py       # RunState, Finalization, transitions, RunRecord
│   │   └── revision.py        # compute_revision (the only hashing module)
│   └── ports/             # the interfaces the flow consumes
│       ├── clock.py           # Clock
│       ├── provider.py        # WorkItemProvider
│       ├── executor.py        # Executor
│       ├── state.py           # RunStateStore, LeaseStore, Lease
│       ├── secrets.py         # SecretStore
│       ├── artifacts.py       # ArtifactStore
│       └── roles.py           # Role
├── runtime/
│   ├── definition.py      # AutomationDefinition
│   ├── service.py         # RunService: the eleven steps
│   └── dispatch.py        # DeliveredEvent, Dispatcher (event and schedule to trigger)
├── roles/
│   └── synthetic.py       # one representative role
└── fakes/                 # in-memory implementations of every port
    ├── local.py           # build_local_environment: the offline operator flow
    └── clock.py, provider.py, state.py, secrets.py, artifacts.py, executor.py
```

Tests:

```
tests/
├── core/                  # domain unit tests, the state machine, the import boundaries
├── runtime/               # the eleven steps, failures, idempotency, leases, security, triggers
├── contracts/             # reusable suites any adapter runs unchanged, plus the fake runners
├── interfaces/            # the CLI contract and the install script
└── fixtures/              # negative fixtures the import-boundary check is pointed at
```

## Dependency direction

Dependencies point inwards, towards `core`, which depends on nothing but the standard library and
other `core` modules:

- `core` contains domain logic and the ports. It does not access the environment or the
  filesystem, and it does not import `runtime`, `roles`, `fakes`, `cli` or `profiles`.
- `runtime` orchestrates a run. It may use core, and it must not import `roles`, `fakes` or `cli`.
- `roles` contain a role. A role never publishes, and a role imports no other role.
- `fakes` provide in-memory ports. They may use core, runtime and roles.
- `cli` is the public entry point, the only place that reads environment variables (locale only)
  and builds a `fakes` environment. Users run `greenhouses`, never `python` or `uv run`.

These boundaries are checked by `tests/core/test_imports.py`, which parses the source and, for
the core boundary, also forbids the standard-library modules that would give core network,
process, filesystem or environment access (`socket`, `ssl`, `http`, `urllib`, `subprocess`, `os`,
`pathlib`, `shutil`, `tempfile`). Negative fixtures under `tests/fixtures/` prove the check fails
when a boundary is broken. `tests/core/test_single_revision_source.py` proves that only
`core/domain/revision.py` imports a hashing module.

## The run lifecycle

A run has eleven ordered steps. Each step is a `RunState`, and every failure also ends at
`finalized`:

| Step | Action | State |
| --- | --- | --- |
| 1 | receive a normalized trigger | `received` |
| 2 | resolve the automation and the role | `resolved` |
| 3 | load and validate versioned configuration | `configured` |
| 4 | resolve the input snapshot and the execution policy | `prepared` |
| 5 | acquire the required state or lease | `leased` |
| 6 | grant only the declared, execution-scoped capabilities | `granted` |
| 7 | invoke an executor | `executing` |
| 8 | validate and persist a versioned result artifact | `artifact-persisted` |
| 9 | re-read the work item and validate the result against it | `validated` |
| 10 | publish through the trusted boundary | `published` |
| 11 | persist the final state and release the lease | `finalized` |

`ALLOWED_TRANSITIONS` allows each state's successor or `finalized`, and `finalized` has no
outgoing transition. The terminal outcomes are named by `Finalization`: `published`, `stale`,
`superseded`, `denied`, `failed`, `lease-lost`. The state machine and its outcomes are documented
in [ADR 0001](adr/0001-lifecycle-and-state-machine.md); a test proves every disallowed transition
is rejected.

Step 9 is not decoration: the runner re-reads the work item and compares revisions computed by
`compute_revision`, and publication is step 10, so a result is never published over an item that
changed while the run was in flight. `RunRecord.history` records every state a run passed
through, so all eleven steps are observable.

## Ports and their consumers

Every port has a real caller in the flow (see [ADR 0002](adr/0002-port-boundaries.md) for the
table). `WorkItemProvider` reads work items and performs the privileged publication. `Executor`
is the long-running execution model (`start`, `poll`, `result`, `stop`). `RunStateStore` and
`LeaseStore` hold run records and leases. `SecretStore` resolves secrets for the supervisor only.
`ArtifactStore` persists result artifacts. `Role` produces a payload and never publishes. `Clock`
supplies time so lease expiry is deterministic.

## Security ownership

Control-plane secrets and execution secrets are different abstractions. A run holds the
`SecretStore`; an execution receives only a `GrantedSecrets`, which resolves execution secrets
allowed by an explicit, run-scoped grant and refuses every other scope. Publication happens only
through the trusted boundary, only after step 9. State is ordinary data and never a secret store.
Secret values are redacted from logs, artifacts and error messages. The invariants and their
proofs are in [ADR 0003](adr/0003-security-ownership.md).

## Idempotency and leases

A trigger's `trigger_id` is its idempotency key; a duplicate delivery returns the recorded
outcome without a second run, and a trigger that is not newer than the last finalized one is
recorded as `superseded`. Leases are exclusive per work item, expire, and can be taken over; a
fence prevents a superseded holder from publishing. Idempotency keys and artifact identities are
derived through `compute_revision`. See [ADR 0004](adr/0004-idempotency-and-leases.md).

## The local operator flow

`greenhouses run` is a thin subcommand of the CLI. It builds the fully in-memory environment in
`fakes/local.py` and runs the lifecycle once through the documented contracts, then prints a JSON
summary (the run id, the trigger id, the states, the finalization and the published artifact). It
contains no flow logic, touches no network, filesystem or external service, and exists so a
fuller operator workflow can later be built on the same `RunService`. `--version`, `--help`,
no-argument usage and the exit status for unknown arguments are unchanged.

## Implemented and planned

Implemented:

- The `greenhouses` package at version 0.1.0 and its installable `greenhouses` command, now with
  the `run` subcommand.
- `compute_revision`, the only place a revision is computed.
- The core domain contracts, the state machine and the ports.
- The `runtime` orchestration of the eleven steps, the synthetic role, and in-memory fakes for
  every port.
- Reusable contract suites under `tests/contracts/` that any adapter runs unchanged.
- Clone-based maintainer installation through `install.sh`.

Planned, not implemented:

- Real provider and executor adapters (the ADR on port boundaries fixes the executor contract so
  they can be added without changing it).
- A versioned manifest format and closed configuration schemas
  ([ADR 0005](adr/0005-configuration-boundary.md)).
- The full operator workflow (validate, build, plan, apply, status, dispatch), persistent state
  and the factory roles.
- Profiles and further port catalogue entries, each added together with its first caller.

## Installation

Installation from a clone only. The installed command points at the checkout; network installation
and tagged releases come with the first tag.
