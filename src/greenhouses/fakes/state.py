"""In-memory run-state and lease stores."""

from __future__ import annotations

from datetime import datetime, timedelta

from greenhouses.core.domain.lifecycle import RunRecord, RunState
from greenhouses.core.ports.state import Lease


class InMemoryRunStateStore:
    """Keyed by idempotency key, with the last finalized sequence per item."""

    def __init__(self) -> None:
        self._records: dict[str, RunRecord] = {}
        self._last_sequence: dict[str, int] = {}

    def get(self, trigger_id: str) -> RunRecord | None:
        return self._records.get(trigger_id)

    def begin(self, record: RunRecord) -> tuple[RunRecord, bool]:
        existing = self._records.setdefault(record.trigger_id, record)
        return existing, existing is record

    def put(self, record: RunRecord) -> None:
        self._records[record.trigger_id] = record
        if record.state is RunState.FINALIZED:
            previous = self._last_sequence.get(record.item_id, 0)
            self._last_sequence[record.item_id] = max(previous, record.sequence)

    def last_sequence(self, item_id: str) -> int:
        return self._last_sequence.get(item_id, 0)


class InMemoryLeaseStore:
    """A single-process lease store with a monotonic fence per work item.

    Acquisition is atomic within the process: a live, unexpired lease held by a
    different run is not stolen, and a re-acquisition after expiry bumps the
    fence so the previous holder can never publish.
    """

    def __init__(self) -> None:
        self._leases: dict[str, Lease] = {}
        self._fences: dict[str, int] = {}

    def acquire(self, item_id: str, run_id: str, ttl: timedelta, now: datetime) -> Lease | None:
        held = self._leases.get(item_id)
        if held is not None and held.run_id != run_id and held.expires_at > now:
            return None
        fence = self._fences.get(item_id, 0) + 1
        self._fences[item_id] = fence
        lease = Lease(item_id=item_id, run_id=run_id, fence=fence, expires_at=now + ttl)
        self._leases[item_id] = lease
        return lease

    def release(self, lease: Lease) -> None:
        held = self._leases.get(lease.item_id)
        if held is not None and held.fence == lease.fence and held.run_id == lease.run_id:
            del self._leases[lease.item_id]

    def is_current(self, lease: Lease, now: datetime) -> bool:
        held = self._leases.get(lease.item_id)
        return (
            held is not None
            and held.fence == lease.fence
            and held.run_id == lease.run_id
            and held.expires_at > now
        )
