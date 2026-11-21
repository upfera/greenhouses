"""An in-memory work-item provider."""

from __future__ import annotations

from collections.abc import Iterable

from greenhouses.core.domain.errors import StaleWorkItem
from greenhouses.core.domain.publication import Publication, PublicationReceipt
from greenhouses.core.domain.work_item import WorkItem


class InMemoryProvider:
    """Reads and publishes against items held in a dictionary.

    ``publish`` compares the current item's revision with the publication's
    expected revision, so a publication against a moved item is rejected even
    if a run somehow skipped its own validation.
    """

    def __init__(self, items: Iterable[WorkItem] = ()) -> None:
        self._items: dict[str, WorkItem] = {item.item_id: item for item in items}
        self.publications: list[Publication] = []

    def read(self, item_id: str) -> WorkItem | None:
        return self._items.get(item_id)

    def write(self, item: WorkItem) -> None:
        """Replace an item, simulating an external change during a run."""
        self._items[item.item_id] = item

    def publish(self, publication: Publication) -> PublicationReceipt:
        item = self._items.get(publication.item_id)
        if item is None or item.revision != publication.expected_revision:
            raise StaleWorkItem(f"the work item {publication.item_id!r} moved before publication")
        self.publications.append(publication)
        return PublicationReceipt(
            item_id=publication.item_id,
            revision=item.revision,
            artifact_id=publication.artifact_id,
        )
