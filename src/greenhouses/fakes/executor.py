"""An in-memory executor that runs a role synchronously.

It models the long-running contract over a single call: ``start`` runs the role
and records the outcome, ``poll`` reports it, and ``result`` returns it. A real
executor implements the same four operations over its own lifecycle.

A role that fails is reported as a failed execution, never as a crash: the
executor is a boundary, and a boundary reports failure as state.
"""

from __future__ import annotations

from dataclasses import dataclass

from greenhouses.core.domain.errors import ExecutionFailed
from greenhouses.core.domain.execution import (
    ExecutionOutput,
    ExecutionRequest,
    ExecutionState,
)
from greenhouses.core.ports.roles import Role


@dataclass(slots=True)
class _Execution:
    state: ExecutionState
    output: ExecutionOutput | None = None
    detail: str = ""


class InMemoryExecutor:
    """Runs a role in-process and exposes the executor contract over it."""

    def __init__(self, role: Role) -> None:
        self._role = role
        self._executions: dict[str, _Execution] = {}
        self._counter = 0
        self.stopped: list[str] = []

    def start(self, request: ExecutionRequest) -> str:
        self._counter += 1
        execution_id = f"execution-{self._counter}"
        try:
            payload = self._role.produce(request)
        except Exception as error:  # noqa: BLE001 - a boundary reports failure, not a crash
            self._executions[execution_id] = _Execution(
                state=ExecutionState.FAILED,
                detail=f"the role failed with {type(error).__name__}",
            )
            return execution_id
        output = ExecutionOutput(item_id=request.snapshot.item_id, payload=payload)
        self._executions[execution_id] = _Execution(state=ExecutionState.SUCCEEDED, output=output)
        return execution_id

    def poll(self, execution_id: str) -> ExecutionState:
        return self._executions[execution_id].state

    def result(self, execution_id: str) -> ExecutionOutput:
        execution = self._executions[execution_id]
        if execution.state is not ExecutionState.SUCCEEDED or execution.output is None:
            raise ExecutionFailed(execution.detail or f"the execution is {execution.state.value!r}")
        return execution.output

    def stop(self, execution_id: str) -> None:
        # The in-memory executor finishes inside ``start``, so there is nothing
        # left to stop; it records the request so a test can observe the call.
        self.stopped.append(execution_id)
