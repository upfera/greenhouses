"""Failure at every step persists a defined final state and releases the lease."""

from __future__ import annotations

from datetime import timedelta

from support import (
    CAPABILITY,
    EPOCH,
    ClockAdvancingExecutor,
    CrashingExecutor,
    FailingExecutor,
    Harness,
    MutatingProvider,
    NeverFinishingExecutor,
    RogueExecutor,
    build_harness,
    default_definition,
    default_item,
    deliver,
    moved_item,
)

from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.lifecycle import Finalization, RunRecord, RunState
from greenhouses.core.domain.secrets import Capability, SecretScope
from greenhouses.fakes.clock import ManualClock
from greenhouses.fakes.executor import InMemoryExecutor
from greenhouses.roles.synthetic import SyntheticRole


def _assert_finalized(record: RunRecord, outcome: Finalization) -> None:
    assert record.state is RunState.FINALIZED
    assert record.finalization is outcome
    assert not record.history or record.history[-1] is RunState.FINALIZED


def _assert_lease_released(harness: Harness) -> None:
    probe = harness.leases.acquire(
        harness.item_id, "probe", timedelta(seconds=60), harness.clock.now()
    )
    assert probe is not None, "the run did not release its lease"
    harness.leases.release(probe)


def test_an_unknown_automation_fails() -> None:
    harness = build_harness()

    record = deliver(harness, automation=AutomationId("absent"))

    _assert_finalized(record, Finalization.FAILED)
    assert harness.provider.publications == []


def test_an_unsupported_configuration_version_fails() -> None:
    harness = build_harness(definition=default_definition(configuration_version="99"))

    record = deliver(harness)

    _assert_finalized(record, Finalization.FAILED)
    assert harness.provider.publications == []


def test_a_missing_work_item_fails() -> None:
    harness = build_harness()

    record = deliver(harness, item_id="absent-item")

    _assert_finalized(record, Finalization.FAILED)
    assert harness.provider.publications == []


def test_a_lease_held_by_another_run_denies_the_run() -> None:
    harness = build_harness()
    held = harness.leases.acquire(
        harness.item_id, "other-run", timedelta(seconds=60), harness.clock.now()
    )
    assert held is not None

    record = deliver(harness)

    _assert_finalized(record, Finalization.DENIED)
    assert harness.provider.publications == []


def test_an_unsupported_permission_scope_denies_the_grant() -> None:
    definition = default_definition(
        capabilities=(
            Capability(CAPABILITY, secret="supervisor-secret", scope=SecretScope.CONTROL_PLANE),
        )
    )
    harness = build_harness(definition=definition)

    record = deliver(harness)

    _assert_finalized(record, Finalization.DENIED)
    assert harness.provider.publications == []
    _assert_lease_released(harness)


def test_an_executor_failure_is_finalized_and_the_lease_released() -> None:
    harness = build_harness(executor=FailingExecutor())

    record = deliver(harness)

    _assert_finalized(record, Finalization.FAILED)
    assert harness.provider.publications == []
    _assert_lease_released(harness)


def test_an_execution_that_never_finishes_is_stopped_and_fails() -> None:
    executor = NeverFinishingExecutor()
    harness = build_harness(executor=executor)

    record = deliver(harness)

    _assert_finalized(record, Finalization.FAILED)
    assert executor.stopped == ["never"]
    assert harness.provider.publications == []
    _assert_lease_released(harness)


def test_an_unexpected_port_error_fails_closed_without_leaking_it() -> None:
    harness = build_harness(executor=CrashingExecutor())

    record = deliver(harness)

    _assert_finalized(record, Finalization.FAILED)
    assert "RuntimeError" in record.detail
    assert "misbehaved" not in record.detail
    assert harness.provider.publications == []
    _assert_lease_released(harness)


def test_a_result_for_another_work_item_is_rejected() -> None:
    harness = build_harness(executor=RogueExecutor("somewhere-else"))

    record = deliver(harness)

    _assert_finalized(record, Finalization.FAILED)
    assert harness.provider.publications == []


def test_a_work_item_that_changed_during_the_run_is_not_published() -> None:
    provider = MutatingProvider([default_item()], moved_item(), after_read=1)
    harness = build_harness(provider=provider)

    record = deliver(harness)

    _assert_finalized(record, Finalization.STALE)
    assert harness.provider.publications == []
    _assert_lease_released(harness)


def test_a_publication_rejected_by_the_provider_is_stale() -> None:
    provider = MutatingProvider([default_item()], moved_item(), after_read=2)
    harness = build_harness(provider=provider)

    record = deliver(harness)

    _assert_finalized(record, Finalization.STALE)
    assert harness.provider.publications == []


def test_a_lease_that_expires_during_the_run_cannot_publish() -> None:
    clock = ManualClock(EPOCH)
    inner = InMemoryExecutor(SyntheticRole())
    executor = ClockAdvancingExecutor(inner, clock, timedelta(seconds=61))
    harness = build_harness(clock=clock, executor=executor)

    record = deliver(harness)

    _assert_finalized(record, Finalization.LEASE_LOST)
    assert harness.provider.publications == []
    _assert_lease_released(harness)
