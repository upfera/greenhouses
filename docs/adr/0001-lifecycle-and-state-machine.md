# ADR 0001: The run lifecycle and its state machine

- Status: accepted
- Date: 2026-11-20

## Context

A run has eleven ordered steps: receive a normalized trigger, resolve the automation and the
role, load and validate versioned configuration, resolve the input snapshot and the execution
policy, acquire the required state or lease, grant only the declared execution-scoped
capabilities, invoke an executor, validate and persist a versioned result artifact, re-read the
work item and validate the result against it, publish through the trusted boundary, then
persist the final state and release the lease.

Every path must end at step 11, including every failure, and the set of outcomes must be named
rather than inferred. The state machine is the contract that makes that observable: it is data,
not a narrative, so a test can prove that every disallowed transition is rejected.

## Decision

The lifecycle is a closed state machine in `greenhouses.core.domain.lifecycle`.

`RunState` names each step, in order: `received`, `resolved`, `configured`, `prepared`,
`leased`, `granted`, `executing`, `artifact-persisted`, `validated`, `published`,
`finalized`.

`ALLOWED_TRANSITIONS` is the only source of truth. Each state advances to its successor, or
ends at `finalized`. `finalized` has no outgoing transition, so a finalized run is never
re-entered; a duplicate delivery is a read of the recorded record, not a second run.
`can_transition` asks the question and `require_transition` enforces it, raising
`InvalidTransition` for anything else. The state machine is only ever advanced through
`require_transition`, so an illegal move fails immediately rather than being recorded.

`Finalization` names the terminal outcomes, recorded when the run reaches `finalized`:

| Outcome | Meaning |
| --- | --- |
| `published` | the result was validated and publication succeeded |
| `stale` | the work item moved before publication, or the provider rejected the publication |
| `superseded` | an older trigger arrived after a newer one had already finalized |
| `denied` | the lease was held elsewhere, or a grant was undeclared or mis-scoped |
| `failed` | configuration, the work item, the executor or the result failed the contract |
| `lease-lost` | the lease expired or was taken over before publication |

The runtime maps a failure to an outcome by error type in one place
(`service._ERROR_OUTCOMES`): `LeaseLost` to `lease-lost`, `StaleWorkItem` to `stale`,
`LeaseUnavailable`, `InvalidGrant` and `SecretAccessDenied` to `denied`, and every other
`GreenhousesError` to `failed`. An error that is not a domain error still ends the run as
`failed`, but its message is dropped (`RunService` catches it at the trust boundary and
records only the error's type), because a boundary's exception text is not trustworthy state.

Failure handling is therefore uniform: `try` covers steps 2 to 10, `except` finalizes, and
`finally` releases the lease if one was acquired. A run never leaves a lease held, whether it
published, declined or crashed.

`RunRecord` is the observable state of a run: the idempotency key, the trigger, the work item,
the sequence, the current state, the finalization once terminal, a detail string, and the full
history of states. `history` is what "all eleven steps are observable" means in tests.

## Consequences

- A test enumerates all state pairs and proves every disallowed transition raises.
- Every failure path is one code path, so it is hard to add a step that can fail without
  finalizing.
- `finalized` being terminal is what makes duplicate delivery cheap and safe.
- The detail string is deliberately terse: it must never carry a secret value, so unexpected
  errors contribute only their type.
