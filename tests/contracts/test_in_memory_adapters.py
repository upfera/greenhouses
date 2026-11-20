"""Run every reusable contract suite against the in-memory fakes.

A later real adapter runs the same suites unchanged by implementing the same
fixtures; nothing here reaches into the fakes' internals.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from artifacts_contract import ArtifactStoreContract
from executor_contract import ExecutorContract
from provider_contract import CONTRACT_ITEM, ProviderContract
from secrets_contract import CONTRACT_SECRET, CONTRACT_SECRET_VALUE, SecretStoreContract
from state_contract import LeaseStoreContract, RunStateStoreContract

from greenhouses.core.ports.executor import Executor
from greenhouses.core.ports.roles import Role
from greenhouses.fakes.artifacts import InMemoryArtifactStore
from greenhouses.fakes.executor import InMemoryExecutor
from greenhouses.fakes.provider import InMemoryProvider
from greenhouses.fakes.secrets import InMemorySecretStore
from greenhouses.fakes.state import InMemoryLeaseStore, InMemoryRunStateStore


class TestInMemoryProvider(ProviderContract):
    @pytest.fixture
    def provider(self) -> InMemoryProvider:
        return InMemoryProvider([CONTRACT_ITEM])


class TestInMemoryExecutor(ExecutorContract):
    @pytest.fixture
    def executor_factory(self) -> Callable[[Role], Executor]:
        return InMemoryExecutor


class TestInMemoryRunStateStore(RunStateStoreContract):
    @pytest.fixture
    def store(self) -> InMemoryRunStateStore:
        return InMemoryRunStateStore()


class TestInMemoryLeaseStore(LeaseStoreContract):
    @pytest.fixture
    def leases(self) -> InMemoryLeaseStore:
        return InMemoryLeaseStore()


class TestInMemorySecretStore(SecretStoreContract):
    @pytest.fixture
    def store(self) -> InMemorySecretStore:
        return InMemorySecretStore({CONTRACT_SECRET: CONTRACT_SECRET_VALUE})


class TestInMemoryArtifactStore(ArtifactStoreContract):
    @pytest.fixture
    def store(self) -> InMemoryArtifactStore:
        return InMemoryArtifactStore()
