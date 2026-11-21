"""The provider boundary: work-item reads and privileged publication.

A provider owns the external system. A run reads through it and publishes
through it; an execution never publishes directly. The provider is the trusted
boundary that performs the side effect, after a run has validated its result.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from greenhouses.core.domain.publication import Publication, PublicationReceipt
from greenhouses.core.domain.work_item import WorkItem


@runtime_checkable
class WorkItemProvider(Protocol):
    """Reads work items and publishes results."""

    def read(self, item_id: str) -> WorkItem | None:
        """Return the current item, or ``None`` when it does not exist."""
        ...

    def publish(self, publication: Publication) -> PublicationReceipt:
        """Perform the privileged publication, or raise ``StaleWorkItem``."""
        ...
