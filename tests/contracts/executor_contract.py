"""Reusable contract suite for ``Executor``.

Any adapter runs this suite unchanged by subclassing ``ExecutorContract`` and
supplying an ``executor_factory`` fixture that builds the adapter around a
given role.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import pytest

from greenhouses.core.domain.artifact import JsonValue
from greenhouses.core.domain.errors import ExecutionFailed, SecretAccessDenied
from greenhouses.core.domain.execution import (
    ExecutionOutput,
    ExecutionRequest,
    ExecutionState,
    InputSnapshot,
)
from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.secrets import SecretRef, granted_secrets
from greenhouses.core.domain.work_item import Revision
from greenhouses.core.ports.executor import Executor
from greenhouses.core.ports.roles import Role

CONTRACT_ITEM_ID = "contract-item"


class _NoSecrets:
    def resolve(self, reference: SecretRef) -> object:
        raise SecretAccessDenied("the executor contract grants no secrets")


class _EchoRole:
    name = "echo"

    def produce(self, request: ExecutionRequest) -> Mapping[str, JsonValue]:
        return {"item_id": request.snapshot.item_id}


class _FailingRole:
    name = "failing"

    def produce(self, request: ExecutionRequest) -> Mapping[str, JsonValue]:
        raise RuntimeError("the role could not run")


def contract_request() -> ExecutionRequest:
    return ExecutionRequest(
        run_id="run-1",
        automation=AutomationId("contract"),
        role="echo",
        snapshot=InputSnapshot(
            item_id=CONTRACT_ITEM_ID,
            revision=Revision("revision"),
            fields={"title": "Contract"},
        ),
        secrets=granted_secrets(run_id="run-1", grants=(), store=_NoSecrets()),
    )


def _settle(executor: Executor, execution_id: str) -> ExecutionState:
    state = executor.poll(execution_id)
    for _ in range(1000):
        if state is not ExecutionState.RUNNING:
            break
        state = executor.poll(execution_id)
    return state


class ExecutorContract:
    """Behaviours every executor adapter must have."""

    @pytest.fixture
    def executor_factory(self) -> Callable[[Role], Executor]:
        raise NotImplementedError("an executor adapter must supply its factory")

    def test_a_successful_execution_yields_its_output(
        self, executor_factory: Callable[[Role], Executor]
    ) -> None:
        executor = executor_factory(_EchoRole())
        execution_id = executor.start(contract_request())

        assert _settle(executor, execution_id) is ExecutionState.SUCCEEDED
        output: ExecutionOutput = executor.result(execution_id)
        assert output.item_id == CONTRACT_ITEM_ID
        assert output.payload["item_id"] == CONTRACT_ITEM_ID

    def test_a_failing_execution_is_reported_as_failed(
        self, executor_factory: Callable[[Role], Executor]
    ) -> None:
        executor = executor_factory(_FailingRole())
        execution_id = executor.start(contract_request())

        assert _settle(executor, execution_id) is ExecutionState.FAILED
        with pytest.raises(ExecutionFailed):
            executor.result(execution_id)

    def test_stop_is_safe_after_completion(
        self, executor_factory: Callable[[Role], Executor]
    ) -> None:
        executor = executor_factory(_EchoRole())
        execution_id = executor.start(contract_request())
        _settle(executor, execution_id)

        executor.stop(execution_id)
