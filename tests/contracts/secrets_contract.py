"""Reusable contract suite for ``SecretStore``.

An adapter runs this suite unchanged by subclassing ``SecretStoreContract`` and
supplying a ``store`` fixture seeded with ``CONTRACT_SECRET``.
"""

from __future__ import annotations

import pytest

from greenhouses.core.domain.errors import SecretAccessDenied
from greenhouses.core.domain.secrets import SecretRef, SecretScope
from greenhouses.core.ports.secrets import SecretStore

CONTRACT_SECRET = SecretRef("contract-secret", SecretScope.EXECUTION)
CONTRACT_SECRET_VALUE = "contract-secret-value"


class SecretStoreContract:
    """Behaviours every secret-store adapter must have."""

    @pytest.fixture
    def store(self) -> SecretStore:
        raise NotImplementedError("a secret adapter must supply its implementation")

    def test_resolves_a_seeded_secret(self, store: SecretStore) -> None:
        value = store.resolve(CONTRACT_SECRET)
        assert value.reference == CONTRACT_SECRET
        assert value.value == CONTRACT_SECRET_VALUE

    def test_an_unknown_secret_is_denied(self, store: SecretStore) -> None:
        with pytest.raises(SecretAccessDenied):
            store.resolve(SecretRef("absent-secret"))

    def test_the_value_is_redacted_in_repr_and_str(self, store: SecretStore) -> None:
        value = store.resolve(CONTRACT_SECRET)
        assert CONTRACT_SECRET_VALUE not in repr(value)
        assert CONTRACT_SECRET_VALUE not in str(value)
