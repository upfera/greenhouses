"""Concurrency, expiry and takeover of leases."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from support import (
    EPOCH,
    build_harness,
    default_definition,
    default_item,
    deliver,
)

from greenhouses.core.domain.artifact import JsonValue
from greenhouses.core.domain.execution import ExecutionOutput, ExecutionRequest, ExecutionState
from greenhouses.core.domain.lifecycle import Finalization, RunRecord
from greenhouses.core.ports.executor import Executor
from greenhouses.core.ports.state import Lease, LeaseStore
from greenhouses.fakes.clock import ManualClock
from greenhouses.fakes.executor import InMemoryExecutor
from greenhouses.fakes.state import InMemoryLeaseStore
from greenhouses.roles.synthetic import SyntheticRole


class ReentrantRole:
    """A role that, while running, tries to start a second run of the same item."""

    name = "reentrant"

    def __init__(self) -> None:
        self.run: Callable[[], RunRecord] | None = None
        self.concurrent: RunRecord | None = None

    def produce(self, request: ExecutionRequest) -> dict[str, JsonValue]:
        runner = self.run
        if runner is not None:
            self.concurrent = runner()
        return {"role": self.name}


class TakeoverExecutor:
    """Expires the lease mid-run and lets another run take it over."""

    def __init__(
        self, inner: Executor, leases: LeaseStore, clock: ManualClock, ttl: timedelta
    ) -> None:
        self._inner = inner
        self._leases = leases
        self._clock = clock
        self._ttl = ttl
        self.taken: Lease | None = None

    def start(self, request: ExecutionRequest) -> str:
        execution_id = self._inner.start(request)
        self._clock.advance(self._ttl + timedelta(seconds=1))
        self.taken = self._leases.acquire(
            request.snapshot.item_id, "run-b", self._ttl, self._clock.now()
        )
        return execution_id

    def poll(self, execution_id: str) -> ExecutionState:
        return self._inner.poll(execution_id)

    def result(self, execution_id: str) -> ExecutionOutput:
        return self._inner.result(execution_id)

    def stop(self, execution_id: str) -> None:
        self._inner.stop(execution_id)


def test_a_second_run_cannot_take_a_held_lease() -> None:
    role = ReentrantRole()
    harness = build_harness(role=role, definition=default_definition(role=role.name))
    role.run = lambda: deliver(harness, trigger_id="event:concurrent", sequence=1)

    record = deliver(harness)

    assert record.finalization is Finalization.PUBLISHED
    assert role.concurrent is not None
    assert role.concurrent.finalization is Finalization.DENIED
    assert len(harness.provider.publications) == 1


def test_a_taken_over_lease_cannot_publish() -> None:
    clock = ManualClock(EPOCH)
    leases = InMemoryLeaseStore()
    executor = TakeoverExecutor(
        InMemoryExecutor(SyntheticRole()), leases, clock, timedelta(seconds=60)
    )
    harness = build_harness(clock=clock, leases=leases, executor=executor)

    record = deliver(harness)

    assert executor.taken is not None, "the second run should have acquired the lease"
    assert record.finalization is Finalization.LEASE_LOST
    assert harness.provider.publications == []


def test_a_run_releases_its_lease_for_the_next_attempt() -> None:
    harness = build_harness()

    first = deliver(harness, trigger_id="event:a", sequence=1)
    second = deliver(harness, trigger_id="event:b", sequence=2)

    assert first.finalization is Finalization.PUBLISHED
    assert second.finalization is Finalization.PUBLISHED


def test_two_items_do_not_block_each_other() -> None:
    harness = build_harness(items=[default_item("item-1"), default_item("item-2")])

    first = deliver(harness, trigger_id="event:1", item_id="item-1")
    second = deliver(harness, trigger_id="event:2", item_id="item-2")

    assert first.finalization is Finalization.PUBLISHED
    assert second.finalization is Finalization.PUBLISHED
    assert len(harness.provider.publications) == 2
