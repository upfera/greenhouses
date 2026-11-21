"""Duplicate delivery and out-of-order triggers."""

from __future__ import annotations

from support import FailingExecutor, build_harness, deliver

from greenhouses.core.domain.lifecycle import Finalization


def test_duplicate_delivery_produces_one_publication_effect() -> None:
    harness = build_harness()

    first = deliver(harness)
    second = deliver(harness)

    assert first.finalization is Finalization.PUBLISHED
    assert second == first
    assert len(harness.provider.publications) == 1


def test_a_duplicate_delivery_does_not_re_run_the_executor() -> None:
    harness = build_harness()

    deliver(harness)
    deliver(harness)

    executor = harness.executor
    assert len(executor._executions) == 1  # type: ignore[attr-defined]


def test_a_duplicate_of_a_failed_run_returns_the_recorded_outcome() -> None:
    harness = build_harness(executor=FailingExecutor())

    first = deliver(harness)
    second = deliver(harness)

    assert first.finalization is Finalization.FAILED
    assert second == first
    assert harness.provider.publications == []


def test_an_older_trigger_after_a_newer_one_does_not_regress_state() -> None:
    harness = build_harness()

    newer = deliver(harness, sequence=5)
    older = deliver(harness, sequence=2)

    assert newer.finalization is Finalization.PUBLISHED
    assert older.finalization is Finalization.SUPERSEDED
    assert len(harness.provider.publications) == 1


def test_a_newer_trigger_after_an_older_run_is_not_superseded() -> None:
    harness = build_harness()

    first = deliver(harness, trigger_id="event:a", sequence=1)
    second = deliver(harness, trigger_id="event:b", sequence=2)

    assert first.finalization is Finalization.PUBLISHED
    assert second.finalization is Finalization.PUBLISHED
    assert len(harness.provider.publications) == 2
