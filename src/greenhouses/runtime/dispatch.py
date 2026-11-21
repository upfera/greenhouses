"""Normalizing delivered events and scheduled scans into triggers.

Both entry points produce the same normalized trigger, so a scheduled scan and
a delivered event drive the same run. The dispatcher is the only place a
trigger is built.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from greenhouses.core.domain.errors import WorkItemNotFound
from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.lifecycle import RunRecord
from greenhouses.core.domain.revision import compute_revision
from greenhouses.core.domain.trigger import Trigger, TriggerSource
from greenhouses.core.ports.provider import WorkItemProvider
from greenhouses.runtime.service import RunService


@dataclass(frozen=True, slots=True)
class DeliveredEvent:
    """An event already normalized by an event source, ready to become a trigger."""

    event_id: str
    automation: AutomationId
    item_id: str
    sequence: int
    parameters: Mapping[str, str] = field(default_factory=dict)


class Dispatcher:
    """Turns events and scans into normalized triggers and runs them."""

    def __init__(self, service: RunService, provider: WorkItemProvider) -> None:
        self._service = service
        self._provider = provider

    def deliver(self, event: DeliveredEvent) -> RunRecord:
        """Run the automation for a delivered event."""
        trigger = Trigger(
            trigger_id=f"event:{event.event_id}",
            automation=event.automation,
            item_id=event.item_id,
            source=TriggerSource.EVENT,
            sequence=event.sequence,
            parameters=event.parameters,
        )
        return self._service.run(trigger)

    def scan(self, automation: AutomationId, item_id: str, sequence: int) -> RunRecord:
        """Run the automation for a work item found by a scheduled scan.

        The trigger's idempotency key is derived from the item's current
        revision through ``compute_revision``, so rescanning an unchanged item
        is a duplicate delivery rather than a second run.
        """
        item = self._provider.read(item_id)
        if item is None:
            raise WorkItemNotFound(f"no work item {item_id!r}")
        key = compute_revision(automation.name, item.revision.value, (item_id,), "")
        trigger = Trigger(
            trigger_id=f"schedule:{key}",
            automation=automation,
            item_id=item_id,
            source=TriggerSource.SCHEDULE,
            sequence=sequence,
        )
        return self._service.run(trigger)
