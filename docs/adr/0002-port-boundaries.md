# ADR 0002: Port boundaries and their first consumers

- Status: accepted
- Date: 2026-11-20

## Context

The flow must integrate with systems it does not own: a provider that holds work items and
performs privileged publication, an executor that runs work in isolation, persistence for run
state and leases, secret resolution, and artifact storage. Each of these is a port. A port is
only added when the flow consumes it, with a real call site, so the interfaces describe real
needs rather than a speculative catalogue.

## Decision

Ports live in `greenhouses.core.ports`, are standard-library only, and are consumed by the
runtime (and, for the role contract, by an executor adapter):

| Port | Operations | First consumer |
| --- | --- | --- |
| `WorkItemProvider` | `read`, `publish` | `RunService` (steps 4, 9, 10) and `Dispatcher` (a scheduled scan reads the item to derive the trigger) |
| `Executor` | `start`, `poll`, `result`, `stop` | `RunService` (step 7) |
| `RunStateStore` | `get`, `put`, `last_sequence` | `RunService` (record keeping, duplicate and out-of-order handling) |
| `LeaseStore` | `acquire`, `release`, `is_current` | `RunService` (steps 5, 10, and release) |
| `SecretStore` | `resolve` | `RunService` builds `GrantedSecrets` from it (step 6) |
| `ArtifactStore` | `save`, `load` | `RunService` (step 8) |
| `Role` | `produce` | the executor adapter drives it (`InMemoryExecutor` here) |
| `Clock` | `now` | `RunService`, for deterministic lease timing |

Core defines the protocols and the domain types they exchange. It never imports an adapter;
`greenhouses.fakes` provides in-memory implementations, and a real adapter will provide others.

### The long-running execution model

An execution is not a function call. `Executor.start` returns an opaque execution id,
`poll` reports an `ExecutionState` (`running`, `succeeded`, `failed`, `stopped`), `result`
returns an `ExecutionOutput` for a successful execution, and `stop` ends one that has not
finished. The runtime polls within a bounded budget and calls `stop` when the budget is
exhausted, then fails closed.

A synchronous adapter implements the four operations over a single call; the in-memory
`InMemoryExecutor` does exactly that. A real executor maps the same four operations onto its
own lifecycle without changing the contract. Because the contract is the operations and not
"one blocking call", a real executor can be adapted later without a breaking change.

An executor never publishes and never sees a secret store; it receives an `ExecutionRequest`
whose `secrets` is a `GrantedSecrets`. Publication is a separate, trusted-boundary operation on
`WorkItemProvider`.

### How a trigger arises

Both entry points normalize into the same `Trigger` in `greenhouses.runtime.dispatch`, which is
the only place a trigger is built:

- **A delivered event.** `Dispatcher.deliver` takes a `DeliveredEvent` (already normalized by
  an event source) and forms a trigger with idempotency key `event:<event_id>`.
- **A scheduled scan.** `Dispatcher.scan` reads the work item, derives the key from the item's
  current revision through `compute_revision`, and forms a trigger with key
  `schedule:<key>`. Rescanning an unchanged item therefore reproduces the same key and is a
  duplicate delivery, not a second run.

No webhook server, queue or daemon is built here. An event source and a scheduler are outside
this task; both feed the same normalized trigger.

### Where approval provenance enters

Approval provenance is a **policy input**, not a runtime concept in this task. When the factory
roles are migrated, an approval becomes part of the resolved configuration/policy for a run
(step 3/4) and gates the grant or the publication decision there. It is deliberately not a new
state or a new port now, so the flow is not shaped around a feature that does not yet exist.

## Consequences

- Every declared port has at least one caller, and `tests/contracts/` runs a reusable suite
  against each in-memory implementation.
- Adapting a real executor means implementing four operations and passing the executor
  contract suite unchanged.
- The dispatcher keeps trigger construction in one place, so event and schedule paths cannot
  drift.
