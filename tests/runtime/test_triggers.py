"""A delivered event and a scheduled scan share one normalized trigger path."""

from __future__ import annotations

import pytest
from support import AUTOMATION, ITEM_ID, build_harness, default_item, deliver

from greenhouses.core.domain.errors import WorkItemNotFound
from greenhouses.core.domain.lifecycle import Finalization, RunState
from greenhouses.core.domain.trigger import TriggerSource
from greenhouses.runtime.dispatch import DeliveredEvent

EXPECTED_STATES = (
    RunState.RECEIVED,
    RunState.RESOLVED,
    RunState.CONFIGURED,
    RunState.PREPARED,
    RunState.LEASED,
    RunState.GRANTED,
    RunState.EXECUTING,
    RunState.ARTIFACT_PERSISTED,
    RunState.VALIDATED,
    RunState.PUBLISHED,
    RunState.FINALIZED,
)


def test_a_delivered_event_drives_a_complete_run() -> None:
    harness = build_harness()

    record = harness.dispatcher.deliver(
        DeliveredEvent(event_id="event-1", automation=AUTOMATION, item_id=ITEM_ID, sequence=1)
    )

    assert record.history == EXPECTED_STATES
    assert record.finalization is Finalization.PUBLISHED
    assert len(harness.provider.publications) == 1


def test_a_scheduled_scan_drives_a_complete_run() -> None:
    harness = build_harness()

    record = harness.dispatcher.scan(AUTOMATION, ITEM_ID, sequence=1)

    assert record.history == EXPECTED_STATES
    assert record.finalization is Finalization.PUBLISHED


def test_both_entry_points_share_the_normalized_trigger_path() -> None:
    event_record = build_harness().dispatcher.deliver(
        DeliveredEvent(event_id="event-1", automation=AUTOMATION, item_id=ITEM_ID, sequence=1)
    )
    scan_record = build_harness().dispatcher.scan(AUTOMATION, ITEM_ID, sequence=1)

    assert event_record.history == scan_record.history
    assert event_record.finalization is scan_record.finalization


def test_a_scheduled_scan_of_an_unchanged_item_is_a_duplicate() -> None:
    harness = build_harness()

    first = harness.dispatcher.scan(AUTOMATION, ITEM_ID, sequence=1)
    second = harness.dispatcher.scan(AUTOMATION, ITEM_ID, sequence=2)

    assert first.trigger_id == second.trigger_id
    assert second == first
    assert len(harness.provider.publications) == 1


def test_a_run_acts_only_on_the_item_its_trigger_names() -> None:
    harness = build_harness(items=[default_item("item-1"), default_item("item-2")])

    record = deliver(
        harness,
        trigger_id="event:item-2",
        item_id="item-2",
        source=TriggerSource.EVENT,
    )

    assert record.item_id == "item-2"
    assert record.finalization is Finalization.PUBLISHED
    assert [publication.item_id for publication in harness.provider.publications] == ["item-2"]


def test_a_scheduled_scan_of_a_missing_item_cannot_form_a_trigger() -> None:
    harness = build_harness()

    with pytest.raises(WorkItemNotFound):
        harness.dispatcher.scan(AUTOMATION, "absent-item", sequence=1)

    assert harness.provider.publications == []
