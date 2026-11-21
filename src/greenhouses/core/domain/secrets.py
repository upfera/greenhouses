"""Secret references, run-scoped capability grants and the access they unlock.

Two kinds of secret exist and they are never the same abstraction:

* control-plane secrets belong to the supervisor and are never reachable from
  an execution;
* execution secrets are reachable only through an explicit grant scoped to a
  single run.

A secret value is a distinct type whose representation is redacted, and the
store itself is never handed to an executor: an executor receives
``GrantedSecrets``, which can only resolve what its grants allow.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from greenhouses.core.domain.errors import InvalidGrant, SecretAccessDenied

if TYPE_CHECKING:
    from greenhouses.core.ports.secrets import SecretStore


class SecretScope(StrEnum):
    """Who is allowed to resolve a secret."""

    CONTROL_PLANE = "control-plane"
    EXECUTION = "execution"


@dataclass(frozen=True, slots=True, order=True)
class SecretRef:
    """A named secret and the scope it belongs to."""

    name: str
    scope: SecretScope = SecretScope.EXECUTION


@dataclass(frozen=True, slots=True)
class SecretValue:
    """A resolved secret value.

    Its value never appears in ``repr``, ``str`` or an error message; only the
    reference identifies it.
    """

    reference: SecretRef
    value: str

    def __repr__(self) -> str:
        return f"SecretValue(reference={self.reference!r}, value=<redacted>)"

    def __str__(self) -> str:
        return "<redacted>"


@dataclass(frozen=True, slots=True)
class Capability:
    """A declared execution capability and the secret it unlocks.

    A capability is only ever execution-scoped; any other scope is rejected
    when grants are issued.
    """

    name: str
    secret: str = ""
    scope: SecretScope = SecretScope.EXECUTION

    def secret_ref(self) -> SecretRef:
        return SecretRef(name=self.secret or self.name, scope=self.scope)


@dataclass(frozen=True, slots=True)
class CapabilityGrant:
    """One declared capability, scoped to a single run."""

    run_id: str
    capability: str
    secret: SecretRef


def issue_grants(run_id: str, capabilities: Iterable[Capability]) -> tuple[CapabilityGrant, ...]:
    """Turn declared capabilities into run-scoped grants.

    An undeclared or mis-scoped capability fails closed with ``InvalidGrant``.
    """
    grants: list[CapabilityGrant] = []
    for capability in capabilities:
        if not capability.name:
            raise InvalidGrant("a capability needs a non-empty name")
        if capability.scope is not SecretScope.EXECUTION:
            raise InvalidGrant(
                f"capability {capability.name!r} has an unsupported permission scope"
            )
        grants.append(
            CapabilityGrant(
                run_id=run_id,
                capability=capability.name,
                secret=capability.secret_ref(),
            )
        )
    return tuple(grants)


@dataclass(frozen=True, slots=True)
class GrantedSecrets:
    """The only secret access an execution has: run-scoped and execution-only."""

    run_id: str
    grants: tuple[CapabilityGrant, ...]
    _values: Mapping[SecretRef, SecretValue]

    def read(self, capability: str) -> SecretValue:
        """Resolve the secret a granted capability unlocks."""
        for grant in self.grants:
            if (
                grant.capability == capability
                and grant.run_id == self.run_id
                and grant.secret.scope is SecretScope.EXECUTION
            ):
                return self._values[grant.secret]
        raise SecretAccessDenied(f"no run-scoped grant for capability {capability!r}")

    def read_reference(self, reference: SecretRef) -> SecretValue:
        """Resolve an execution secret by reference, refusing every other scope."""
        if reference.scope is not SecretScope.EXECUTION:
            raise SecretAccessDenied(
                f"{reference.scope.value} secrets are not available to an execution"
            )
        for grant in self.grants:
            if grant.secret == reference and grant.run_id == self.run_id:
                return self._values[reference]
        raise SecretAccessDenied(f"no run-scoped grant for secret {reference.name!r}")


def granted_secrets(
    run_id: str, grants: tuple[CapabilityGrant, ...], store: SecretStore
) -> GrantedSecrets:
    """Build the execution-facing secret access for one run.

    Every granted reference is resolved here, once, and only the values are handed over.
    The returned object holds no store and no closure over one, so the store cannot be
    reached from an execution even by introspecting it. Isolation from other code in the
    same process is the executor's concern, not this object's; see ADR 0003.
    """
    return GrantedSecrets(
        run_id=run_id,
        grants=grants,
        _values={grant.secret: store.resolve(grant.secret) for grant in grants},
    )
