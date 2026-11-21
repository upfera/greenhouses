"""The unit of work a run acts on, and its content revision.

A trigger is bound to exactly one work item, and a result is validated against
the item's revision. The revision is produced only by ``compute_revision``.
"""

from __future__ import annotations

from dataclasses import dataclass

from greenhouses.core.domain.revision import compute_revision


@dataclass(frozen=True, slots=True, order=True)
class Revision:
    """Content identity of a work item."""

    value: str


@dataclass(frozen=True, slots=True)
class WorkItem:
    """A snapshot of an item, as read from a provider."""

    item_id: str
    title: str
    state: str
    labels: tuple[str, ...]
    body: str

    @property
    def revision(self) -> Revision:
        """Return the revision of this item's content."""
        return Revision(compute_revision(self.title, self.state, list(self.labels), self.body))
