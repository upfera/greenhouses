"""The executor port: the long-running execution model.

An execution is started, polled, stopped and its result read. A synchronous
adapter implements this over one call; a real executor maps it onto its own
lifecycle. The flow consumes all four operations.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from greenhouses.core.domain.execution import ExecutionOutput, ExecutionRequest, ExecutionState


@runtime_checkable
class Executor(Protocol):
    """Runs an execution and reports its outcome."""

    def start(self, request: ExecutionRequest) -> str:
        """Start an execution and return its opaque execution id."""
        ...

    def poll(self, execution_id: str) -> ExecutionState:
        """Return the execution's current state."""
        ...

    def result(self, execution_id: str) -> ExecutionOutput:
        """Return a successful execution's output."""
        ...

    def stop(self, execution_id: str) -> None:
        """Stop an execution that has not finished."""
        ...
