"""The injected clock.

Time enters a run through this port so that lease expiry is deterministic in
tests and a real deployment can supply any clock.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Supplies the current time."""

    def now(self) -> datetime: ...
