"""An in-memory clock whose time only moves when a test moves it."""

from __future__ import annotations

from datetime import datetime, timedelta


class ManualClock:
    """A clock a caller advances explicitly, so lease expiry is deterministic."""

    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta
