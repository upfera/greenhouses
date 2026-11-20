# ADR 0003: Security ownership — supervisor credentials, execution grants and redaction

- Status: accepted
- Date: 2026-11-20

## Context

A run has two very different sides. The supervisor side holds credentials for the control plane:
it reads work items, resolves secrets, keeps run state and leases, and performs the privileged
publication. The execution side runs work in isolation and is, by assumption, untrusted. The
security invariants must hold because of how the flow is wired, and be proven by tests against
observable access and results, not asserted in prose.

## Decision

### Two kinds of credential, two abstractions

`SecretScope` distinguishes `control-plane` secrets from `execution` secrets. They are never the
same abstraction:

- The `SecretStore` is the supervisor-side resolver. `RunService` holds it and hands out only a
  `GrantedSecrets`, never the store itself, to an execution.
- `GrantedSecrets` refuses every scope but `execution` (`read_reference` denies a control-plane
  reference outright) and only resolves what a grant allows. A control-plane secret is therefore
  unreachable from an execution by construction, not by policy. The in-memory store happens to
  hold both kinds, which is exactly why the executor must not receive it.

### Grants are declared and run-scoped

`issue_grants(run_id, capabilities)` turns the declared capabilities of the resolved
configuration into `CapabilityGrant`s, each bound to the run and requiring execution scope. An
undeclared or mis-scoped capability fails closed with `InvalidGrant`. `GrantedSecrets.read`
succeeds only when the capability is granted **and** the grant belongs to this run **and** the
scope is execution. A grant from another run does not unlock anything.

### Privileged effects only through the trusted boundary

Publication is performed by `RunService` (the trusted supervisor) through `WorkItemProvider`,
and only at step 10, after step 9 re-read the work item and validated the result. A `Role` has
no `publish` method and receives no provider: it can produce a payload and nothing else. The
`roles` import boundary enforces the same thing statically.

### Failure is fail-closed

A missing capability, an invalid grant, an unsupported permission scope and an unknown artifact
version all raise rather than degrade: `SecretAccessDenied`, `InvalidGrant` and
`UnknownArtifactVersion` end the run with a defined finalization and no publication. The
`RunService` also catches non-domain exceptions at the boundary and fails the run closed.

### Redaction

A resolved secret is a `SecretValue` whose `repr` and `str` render `<redacted>`; only the
reference identifies it. A failure detail is part of the observable state, so no secret value may
enter it: unexpected boundary errors contribute only their type name. Tests assert that no
seeded secret value appears in an artifact, a run record, a detail string or an error message.

### State is not a secret store

Run state and mutations of it are ordinary data: run and trigger ids, item ids, sequences,
states and revisions. `RunStateStore` records no secret value and is a different abstraction from
`SecretStore`. Keeping them apart is what lets state be inspected, exported and reasoned about
without ever handling a credential.

## Consequences

- The security invariants are properties of the wiring, each with a test that checks the decision
  and the resulting state (an access that is denied, a publication that did not happen).
- `fakes/local.py` and the tests deliberately seed a control-plane secret, so the negative test
  ("the executor could not read it") is meaningful.
- A future real executor receives the same `GrantedSecrets` and inherits the same guarantees.
