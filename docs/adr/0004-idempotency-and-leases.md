# ADR 0004: Idempotency, ordering and leases

- Status: accepted
- Date: 2026-11-20

## Context

Triggers are delivered at least once. The same trigger may arrive twice, and an older trigger may
arrive after a newer one has already completed. A run holds a lease while it works, so two runs
cannot act on one work item at once; leases expire, and an expired one can be taken over.
Idempotency keys and artifact identities must be derived without adding a second place that
computes a revision.

## Decision

### Trigger identity is the idempotency key

A `Trigger` carries a `trigger_id`, which is its idempotency key, and a `sequence`, which orders
triggers for a work item. `Dispatcher` is the only place triggers are built:

- a delivered event uses `event:<event_id>`;
- a scheduled scan uses `schedule:<compute_revision(automation, item.revision, (item_id,), "")>`,
  so an unchanged item rescanned produces the same key.

### Duplicate delivery

`RunService.run` first asks `RunStateStore.get(trigger_id)`. A recorded record is returned
unchanged, so a duplicate delivery performs no second effect and reports the recorded outcome.
Because `finalized` is terminal, a recorded record is always a completed run.

### Out-of-order delivery

`RunService.run` compares `trigger.sequence` with `RunStateStore.last_sequence(item_id)`, the
highest sequence already finalized for the item. A trigger that is not newer is recorded as
`superseded` and does not run, so an older trigger arriving after a newer one neither regresses
state nor republishes. `last_sequence` advances only on finalization, so an in-flight run does not
suppress a legitimate later trigger.

### Leases, expiry and takeover

`LeaseStore.acquire` grants at most one live lease per work item. It refuses to steal a live,
unexpired lease held by a different run, and it bumps a monotonic **fence** on every acquisition,
including after expiry. A lease records `item_id`, `run_id`, `fence` and `expires_at`.

`RunService` re-checks `LeaseStore.is_current(lease, now)` at step 10, immediately before
publishing. A run whose lease expired or was taken over fails the check and finalizes
`lease-lost` without publishing, even though it may have finished its execution. `release` only
removes a lease whose fence and run match, so a superseded holder's late release cannot free the
current holder's lease. Time enters through the injected `Clock`, so expiry is deterministic and
testable.

### Deriving keys without new hashing

The repository rule is that a revision is computed only by `compute_revision` and that no module
outside `core/domain/revision.py` imports `hashlib` or `hmac`. Every identity needed here is
therefore derived through `compute_revision`:

- artifact identity: `compute_revision(version, "artifact", (automation,), canonical_json)`;
- the scheduled-scan trigger key: `compute_revision(automation, item.revision.value, (item_id,), "")`.

`event:<event_id>` is a raw id supplied by the event source, not a derived hash, so it needs no
hashing at all. No new hashing code is introduced.

## Consequences

- "Exactly one publication effect" is a property of the store plus the terminal state, not of a
  distributed transaction: the recorded record is the de-duplication.
- The fence makes takeover safe: an old holder's lease can never be mistaken for the current one.
- A test harness advances a `ManualClock` to exercise expiry and takeover deterministically.
