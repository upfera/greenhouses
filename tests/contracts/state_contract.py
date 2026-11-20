"""Reusable contract suites for ``RunStateStore`` and ``LeaseStore``.

Any adapter runs these suites unchanged by subclassing them and supplying a
``store`` (or ``leases``) fixture.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.lifecycle import Finalization, RunRecord, RunState
from greenhouses.core.ports.state import Lease, LeaseStore, RunStateStore

_ITEM = "contract-item"
_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_TTL = timedelta(seconds=60)


def contract_record(
    trigger_id: str = "trigger-1",
    *,
    item_id: str = _ITEM,
    sequence: int = 1,
    state: RunState = RunState.FINALIZED,
) -> RunRecord:
    return RunRecord(
        run_id=trigger_id,
        trigger_id=trigger_id,
        automation=AutomationId("contract"),
        item_id=item_id,
        sequence=sequence,
        state=state,
        finalization=Finalization.PUBLISHED if state is RunState.FINALIZED else None,
        detail="",
        history=(RunState.RECEIVED, state),
    )


class RunStateStoreContract:
    """Behaviours every run-state adapter must have."""

    @pytest.fixture
    def store(self) -> RunStateStore:
        raise NotImplementedError("a state adapter must supply its implementation")

    def test_a_missing_trigger_is_none(self, store: RunStateStore) -> None:
        assert store.get("absent") is None
        assert store.last_sequence(_ITEM) == 0

    def test_put_then_get_round_trips(self, store: RunStateStore) -> None:
        record = contract_record()
        store.put(record)
        assert store.get(record.trigger_id) == record

    def test_last_sequence_tracks_finalized_records_only(self, store: RunStateStore) -> None:
        store.put(contract_record("in-flight", sequence=5, state=RunState.EXECUTING))
        assert store.last_sequence(_ITEM) == 0

        store.put(contract_record("done", sequence=3))
        assert store.last_sequence(_ITEM) == 3

        store.put(contract_record("older", sequence=1))
        assert store.last_sequence(_ITEM) == 3


class LeaseStoreContract:
    """Behaviours every lease adapter must have."""

    @pytest.fixture
    def leases(self) -> LeaseStore:
        raise NotImplementedError("a lease adapter must supply its implementation")

    def test_acquire_then_is_current(self, leases: LeaseStore) -> None:
        lease = leases.acquire(_ITEM, "run-a", _TTL, _T0)
        assert lease is not None
        assert leases.is_current(lease, _T0)

    def test_a_live_lease_is_not_stolen(self, leases: LeaseStore) -> None:
        first = leases.acquire(_ITEM, "run-a", _TTL, _T0)
        assert first is not None
        assert leases.acquire(_ITEM, "run-b", _TTL, _T0) is None

    def test_release_frees_the_lease(self, leases: LeaseStore) -> None:
        lease = leases.acquire(_ITEM, "run-a", _TTL, _T0)
        assert lease is not None
        leases.release(lease)
        assert not leases.is_current(lease, _T0)
        assert leases.acquire(_ITEM, "run-b", _TTL, _T0) is not None

    def test_an_expired_lease_is_reacquirable_with_a_higher_fence(self, leases: LeaseStore) -> None:
        first = leases.acquire(_ITEM, "run-a", _TTL, _T0)
        assert first is not None
        later = _T0 + _TTL + timedelta(seconds=1)

        assert not leases.is_current(first, later)
        second = leases.acquire(_ITEM, "run-b", _TTL, later)
        assert second is not None
        assert isinstance(second, Lease)
        assert second.fence > first.fence
        assert not leases.is_current(first, later)
        assert leases.is_current(second, later)

    def test_releasing_a_superseded_lease_does_not_free_the_new_one(
        self, leases: LeaseStore
    ) -> None:
        first = leases.acquire(_ITEM, "run-a", _TTL, _T0)
        assert first is not None
        later = _T0 + _TTL + timedelta(seconds=1)
        second = leases.acquire(_ITEM, "run-b", _TTL, later)
        assert second is not None

        leases.release(first)
        assert leases.is_current(second, later)
