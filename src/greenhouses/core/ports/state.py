"""State and lease ports.

Run state records what a run has done, keyed by its idempotency key, and lets a
duplicate delivery read the recorded outcome. Leases serialize runs per work
item; an expired lease can be re-acquired, and the previous holder can no longer
publish.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from greenhouses.core.domain.lifecycle import RunRecord


@dataclass(frozen=True, slots=True)
class Lease:
    """A run's exclusive hold on one work item."""

    item_id: str
    run_id: str
    fence: int
    expires_at: datetime


@runtime_checkable
class RunStateStore(Protocol):
    """Persists run records and the last finalized sequence per work item."""

    def get(self, trigger_id: str) -> RunRecord | None:
        """Return the record for a trigger's idempotency key."""
        ...

    def put(self, record: RunRecord) -> None:
        """Persist a run record."""
        ...

    def last_sequence(self, item_id: str) -> int:
        """Return the highest sequence finalized for a work item, or ``0``."""
        ...


@runtime_checkable
class LeaseStore(Protocol):
    """Acquires, releases and inspects leases per work item."""

    def acquire(self, item_id: str, run_id: str, ttl: timedelta, now: datetime) -> Lease | None:
        """Acquire the lease, or return ``None`` when a live holder owns it."""
        ...

    def release(self, lease: Lease) -> None:
        """Release a held lease."""
        ...

    def is_current(self, lease: Lease, now: datetime) -> bool:
        """Return whether this lease is still held and unexpired."""
        ...
