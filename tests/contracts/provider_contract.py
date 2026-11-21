"""Reusable contract suite for ``WorkItemProvider``.

Any adapter runs this suite unchanged by subclassing ``ProviderContract`` and
supplying a ``provider`` fixture seeded with ``CONTRACT_ITEM``.
"""

from __future__ import annotations

import pytest

from greenhouses.core.domain.errors import StaleWorkItem
from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.publication import Publication
from greenhouses.core.domain.work_item import Revision, WorkItem
from greenhouses.core.ports.provider import WorkItemProvider

CONTRACT_ITEM = WorkItem(
    item_id="contract-item",
    title="Contract item",
    state="open",
    labels=("contract",),
    body="body",
)


def _publication(expected_revision: Revision, item_id: str = CONTRACT_ITEM.item_id) -> Publication:
    return Publication(
        fence=1,
        automation=AutomationId("contract"),
        item_id=item_id,
        expected_revision=expected_revision,
        artifact_id="artifact-1",
        summary="summary",
    )


class ProviderContract:
    """Behaviours every provider adapter must have."""

    @pytest.fixture
    def provider(self) -> WorkItemProvider:
        raise NotImplementedError("a provider adapter must supply its implementation")

    def test_reads_the_seeded_item(self, provider: WorkItemProvider) -> None:
        item = provider.read(CONTRACT_ITEM.item_id)
        assert item == CONTRACT_ITEM
        assert item is not None
        assert item.revision == CONTRACT_ITEM.revision

    def test_reads_a_missing_item_as_none(self, provider: WorkItemProvider) -> None:
        assert provider.read("absent-item") is None

    def test_publish_performs_the_effect_and_receipts_it(self, provider: WorkItemProvider) -> None:
        receipt = provider.publish(_publication(CONTRACT_ITEM.revision))

        assert receipt.item_id == CONTRACT_ITEM.item_id
        assert receipt.revision == CONTRACT_ITEM.revision
        assert receipt.artifact_id == "artifact-1"

    def test_publish_rejects_a_stale_revision(self, provider: WorkItemProvider) -> None:
        publication = _publication(Revision("not-the-current-revision"))

        with pytest.raises(StaleWorkItem):
            provider.publish(publication)

    def test_publish_rejects_an_absent_item(self, provider: WorkItemProvider) -> None:
        publication = _publication(CONTRACT_ITEM.revision, item_id="absent-item")

        with pytest.raises(StaleWorkItem):
            provider.publish(publication)
