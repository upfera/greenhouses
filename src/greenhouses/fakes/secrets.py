"""An in-memory secret store."""

from __future__ import annotations

from collections.abc import Mapping

from greenhouses.core.domain.errors import SecretAccessDenied
from greenhouses.core.domain.secrets import SecretRef, SecretValue


class InMemorySecretStore:
    """Holds both control-plane and execution secrets.

    It is a supervisor-side store: it resolves whatever it is given. Access
    control lives with ``GrantedSecrets``, which an execution is handed instead
    of this store, and which refuses every scope but execution.
    """

    def __init__(self, secrets: Mapping[SecretRef, str] | None = None) -> None:
        self._secrets: dict[SecretRef, str] = dict(secrets or {})

    def resolve(self, reference: SecretRef) -> SecretValue:
        if reference not in self._secrets:
            raise SecretAccessDenied(f"no secret named {reference.name!r}")
        return SecretValue(reference=reference, value=self._secrets[reference])
