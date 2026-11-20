"""Collaborators that let a runtime test steer one run.

Nothing here is a fake of a production interface: the fakes live in ``src``.
These are small, test-only executors used to reach error branches that a
well-behaved executor never takes.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from greenhouses.core.domain.execution import (
    ExecutionOutput,
    ExecutionRequest,
    ExecutionState,
)
from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.lifecycle import RunRecord
from greenhouses.core.domain.secrets import Capability, SecretRef, SecretScope
from greenhouses.core.domain.trigger import Trigger, TriggerSource
from greenhouses.core.domain.work_item import WorkItem
from greenhouses.core.ports.clock import Clock
from greenhouses.core.ports.executor import Executor
from greenhouses.core.ports.roles import Role
from greenhouses.fakes.artifacts import InMemoryArtifactStore
from greenhouses.fakes.clock import ManualClock
from greenhouses.fakes.executor import InMemoryExecutor
from greenhouses.fakes.provider import InMemoryProvider
from greenhouses.fakes.secrets import InMemorySecretStore
from greenhouses.fakes.state import InMemoryLeaseStore, InMemoryRunStateStore
from greenhouses.roles.synthetic import SyntheticRole
from greenhouses.runtime.definition import AutomationDefinition
from greenhouses.runtime.dispatch import Dispatcher
from greenhouses.runtime.service import RunService

EPOCH = datetime(2026, 1, 1, tzinfo=UTC)
AUTOMATION = AutomationId("test-automation")
ITEM_ID = "item-1"
CAPABILITY = "summarize"
EXECUTION_SECRET = SecretRef("execution-secret", SecretScope.EXECUTION)
CONTROL_PLANE_SECRET = SecretRef("supervisor-secret", SecretScope.CONTROL_PLANE)
EXECUTION_SECRET_VALUE = "execution-value"
CONTROL_PLANE_SECRET_VALUE = "supervisor-value"


def default_item(item_id: str = ITEM_ID) -> WorkItem:
    return WorkItem(
        item_id=item_id,
        title="Test item",
        state="open",
        labels=("test",),
        body="body",
    )


def moved_item(item_id: str = ITEM_ID) -> WorkItem:
    """The same item with different content, to move its revision."""
    return WorkItem(
        item_id=item_id,
        title="Test item",
        state="closed",
        labels=("test",),
        body="body",
    )


def default_definition(role: str = "synthetic", **overrides: object) -> AutomationDefinition:
    values: dict[str, object] = {
        "automation": AUTOMATION,
        "role": role,
        "capabilities": (Capability(CAPABILITY, secret=EXECUTION_SECRET.name),),
    }
    values.update(overrides)
    return AutomationDefinition(**values)  # type: ignore[arg-type]


@dataclass
class Harness:
    """Every collaborator a runtime test may inspect or replace."""

    service: RunService
    dispatcher: Dispatcher
    provider: InMemoryProvider
    executor: Executor
    runs: InMemoryRunStateStore
    leases: InMemoryLeaseStore
    secrets: InMemorySecretStore
    artifacts: InMemoryArtifactStore
    clock: ManualClock
    automation: AutomationId
    item_id: str


def build_harness(
    *,
    item: WorkItem | None = None,
    items: Iterable[WorkItem] | None = None,
    role: Role | None = None,
    definition: AutomationDefinition | None = None,
    executor: Executor | None = None,
    clock: ManualClock | None = None,
    secrets: InMemorySecretStore | None = None,
    artifacts: InMemoryArtifactStore | None = None,
    provider: InMemoryProvider | None = None,
    leases: InMemoryLeaseStore | None = None,
) -> Harness:
    """Build an offline run service with a synthetic role and in-memory fakes."""
    chosen_role = role if role is not None else SyntheticRole()
    chosen_item = item if item is not None else default_item()
    if provider is None:
        provider = InMemoryProvider(list(items) if items is not None else [chosen_item])
    chosen_secrets = (
        secrets
        if secrets is not None
        else InMemorySecretStore(
            {
                EXECUTION_SECRET: EXECUTION_SECRET_VALUE,
                CONTROL_PLANE_SECRET: CONTROL_PLANE_SECRET_VALUE,
            }
        )
    )
    chosen_artifacts = artifacts if artifacts is not None else InMemoryArtifactStore()
    chosen_clock = clock if clock is not None else ManualClock(EPOCH)
    chosen_definition = (
        definition if definition is not None else default_definition(role=chosen_role.name)
    )
    chosen_executor = executor if executor is not None else InMemoryExecutor(chosen_role)
    runs = InMemoryRunStateStore()
    chosen_leases = leases if leases is not None else InMemoryLeaseStore()
    service = RunService(
        automations={chosen_definition.automation: chosen_definition},
        provider=provider,
        executor=chosen_executor,
        runs=runs,
        leases=chosen_leases,
        secrets=chosen_secrets,
        artifacts=chosen_artifacts,
        clock=chosen_clock,
    )
    return Harness(
        service=service,
        dispatcher=Dispatcher(service, provider),
        provider=provider,
        executor=chosen_executor,
        runs=runs,
        leases=chosen_leases,
        secrets=chosen_secrets,
        artifacts=chosen_artifacts,
        clock=chosen_clock,
        automation=chosen_definition.automation,
        item_id=chosen_item.item_id,
    )


class RogueExecutor:
    """Returns an output for an item other than the one it was asked about."""

    def __init__(self, item_id: str) -> None:
        self._item_id = item_id

    def start(self, request: ExecutionRequest) -> str:
        return "rogue"

    def poll(self, execution_id: str) -> ExecutionState:
        return ExecutionState.SUCCEEDED

    def result(self, execution_id: str) -> ExecutionOutput:
        return ExecutionOutput(item_id=self._item_id, payload={"rogue": True})

    def stop(self, execution_id: str) -> None:
        return None


class FailingExecutor:
    """Reports a failed execution."""

    def start(self, request: ExecutionRequest) -> str:
        return "failing"

    def poll(self, execution_id: str) -> ExecutionState:
        return ExecutionState.FAILED

    def result(self, execution_id: str) -> ExecutionOutput:
        raise AssertionError("a failed execution has no result")

    def stop(self, execution_id: str) -> None:
        return None


class CrashingExecutor:
    """Raises a non-domain error, to prove the trust boundary fails closed."""

    def start(self, request: ExecutionRequest) -> str:
        return "crashing"

    def poll(self, execution_id: str) -> ExecutionState:
        raise RuntimeError("a port misbehaved")

    def result(self, execution_id: str) -> ExecutionOutput:
        raise AssertionError("a crashing execution has no result")

    def stop(self, execution_id: str) -> None:
        return None


class NeverFinishingExecutor:
    """Stays running forever, so the run must stop it and fail closed."""

    def __init__(self) -> None:
        self.stopped: list[str] = []

    def start(self, request: ExecutionRequest) -> str:
        return "never"

    def poll(self, execution_id: str) -> ExecutionState:
        return ExecutionState.RUNNING

    def result(self, execution_id: str) -> ExecutionOutput:
        raise AssertionError("a running execution has no result")

    def stop(self, execution_id: str) -> None:
        self.stopped.append(execution_id)


class ClockAdvancingExecutor:
    """Delegates to another executor, advancing a clock to simulate elapsed time."""

    def __init__(self, inner: Executor, clock: Clock, delta: timedelta) -> None:
        self._inner = inner
        self._clock = clock
        self._delta = delta

    def start(self, request: ExecutionRequest) -> str:
        execution_id = self._inner.start(request)
        advance = getattr(self._clock, "advance", None)
        if advance is not None:
            advance(self._delta)
        return execution_id

    def poll(self, execution_id: str) -> ExecutionState:
        return self._inner.poll(execution_id)

    def result(self, execution_id: str) -> ExecutionOutput:
        return self._inner.result(execution_id)

    def stop(self, execution_id: str) -> None:
        self._inner.stop(execution_id)


class RecordingRole:
    """A role that records the requests it sees and returns a fixed payload."""

    name = "recording"

    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.requests: list[ExecutionRequest] = []
        self._payload = payload or {"role": "recording"}

    def produce(self, request: ExecutionRequest) -> dict[str, object]:
        self.requests.append(request)
        return dict(self._payload)


def execution_ids(executor: object) -> Sequence[str]:
    """Expose the stopped execution ids of the in-memory executor, if any."""
    stopped = getattr(executor, "stopped", None)
    return stopped if isinstance(stopped, list) else ()


class MutatingProvider(InMemoryProvider):
    """Moves the item after its Nth read, racing a run's validation.

    With ``after_read=1`` the item moves after step 4's snapshot read, so step 9
    sees a change. With ``after_read=2`` it moves after step 9's read, so the
    provider rejects the publication at step 10.
    """

    def __init__(
        self, items: Iterable[WorkItem], moved_item: WorkItem, *, after_read: int = 1
    ) -> None:
        super().__init__(items)
        self._moved_item = moved_item
        self._after_read = after_read
        self._reads = 0

    def read(self, item_id: str) -> WorkItem | None:
        self._reads += 1
        item = super().read(item_id)
        if self._reads == self._after_read:
            super().write(self._moved_item)
        return item


def deliver(
    harness: Harness,
    *,
    sequence: int = 1,
    trigger_id: str | None = None,
    item_id: str | None = None,
    automation: AutomationId | None = None,
    source: TriggerSource = TriggerSource.EVENT,
) -> RunRecord:
    """Run a normalized trigger derived from the harness's defaults."""
    trigger = Trigger(
        trigger_id=trigger_id if trigger_id is not None else f"event:{sequence}",
        automation=automation if automation is not None else harness.automation,
        item_id=item_id if item_id is not None else harness.item_id,
        source=source,
        sequence=sequence,
    )
    return harness.service.run(trigger)
