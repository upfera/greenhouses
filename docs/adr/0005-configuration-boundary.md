# ADR 0005: The configuration boundary

- Status: accepted
- Date: 2026-11-20

## Context

The flow must "load and validate versioned configuration" at step 3 and "resolve the input
snapshot and the execution policy" at step 4. A versioned manifest format and closed
configuration schemas are later work. This task must carry configuration resolution and
validation only as far as the flow needs it, over a minimal automation identity, and must record
any field that only a closed schema could define in an ADR instead of building the schema.

## Decision

The runtime's minimal configuration boundary is two core types plus one runtime type:

- `Configuration(automation, version, role, policy)`. `validated()` fails closed on an unknown
  version, a missing role, or a non-positive lease duration.
- `ExecutionPolicy(capabilities, lease_ttl_seconds)`: the declared capabilities a run may be
  granted and how long its lease lasts.
- `AutomationDefinition`, a runtime view of one automation: its `AutomationId`, the role it runs,
  the `configuration_version` it loads, the capabilities it declares, the parameters it passes to
  an execution, and its lease TTL. `configuration()` builds the `Configuration` the flow
  validates.

The role is a name, the capabilities are declared names with an execution-scoped secret reference,
and parameters are string key-values. There is no schema, no manifest file and no closed
validation: the shape is the smallest one the eleven steps actually consume.

### Fields a closed schema would define

These belong to a later manifest/configuration system and are intentionally not built here. They
are recorded so the follow-up has a place to attach them:

- **Capability permission policy.** Today a capability is a name plus a secret reference and an
  execution scope. A closed schema would define the allowed capability catalogue, the permitted
  scopes and the mapping from capability to permission, so an unknown capability is rejected at
  configuration time rather than at grant time.
- **Lease policy bounds.** Today a lease TTL is any positive integer. A closed schema would set
  permitted bounds and defaults per automation.
- **Execution parameters schema.** Today parameters are free-form strings. A closed schema would
  type and validate them.
- **Approval provenance.** Where an approval enters, and whether it is required, is a policy
  field (see ADR 0002). It is a later configuration concern, not a runtime state now.
- **The manifest itself.** Version selection, identity, and how a definition is loaded from a
  versioned manifest, rather than from an in-code `AutomationDefinition`.

Recording these here is the decision: the flow is deliberately schema-free so that the schema
can be designed against the automations that need it, without reshaping the lifecycle.

## Consequences

- Configuration validation is small and covered, and it cannot silently accept a version it does
  not understand.
- Adding a real manifest later means replacing `AutomationDefinition` construction and widening
  `Configuration`, not changing the lifecycle or the ports.
- The `parameters` mapping flows from a trigger into an `ExecutionRequest` unchanged, ready to be
  validated by a schema later.
