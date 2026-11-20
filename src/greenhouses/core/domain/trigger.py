"""The normalized trigger that starts a run.

A trigger is the single entry point for work, whether it came from a delivered
event or a scheduled scan. It names exactly one automation and one work item.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from greenhouses.core.domain.identity import AutomationId


class TriggerSource(StrEnum):
    """Where a normalized trigger came from."""

    EVENT = "event"
    SCHEDULE = "schedule"


@dataclass(frozen=True, slots=True)
class Trigger:
    """A request to run one automation for exactly one work item.

    ``trigger_id`` is the idempotency key: delivering it twice must produce one
    effect. ``sequence`` orders triggers for a work item; a trigger that is not
    newer than the last finalized one does not run.
    """

    trigger_id: str
    automation: AutomationId
    item_id: str
    source: TriggerSource
    sequence: int
    parameters: Mapping[str, str] = field(default_factory=dict)
