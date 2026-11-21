"""The secret-resolution port.

Only the supervisor holds one. Executions receive ``GrantedSecrets`` instead,
so a control-plane secret is unreachable by construction rather than by policy.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from greenhouses.core.domain.secrets import SecretRef, SecretValue

__all__ = ["SecretRef", "SecretStore"]


@runtime_checkable
class SecretStore(Protocol):
    """Resolves a secret for the supervisor.

    The store is a supervisor-side collaborator; executors never see it and
    therefore never see control-plane secrets.
    """

    def resolve(self, reference: SecretRef) -> SecretValue: ...
