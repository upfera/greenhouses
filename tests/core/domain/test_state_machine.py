"""The documented lifecycle: states, transitions and terminal outcomes."""

from __future__ import annotations

from dataclasses import replace

import pytest

from greenhouses.core.domain.errors import InvalidTransition
from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.lifecycle import (
    ALLOWED_TRANSITIONS,
    FINAL_STATES,
    Finalization,
    RunRecord,
    RunState,
    can_transition,
    require_transition,
)

ALL_STATES = list(RunState)
HAPPY_PATH = [
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
]


def test_every_pair_is_classified_by_the_transition_table() -> None:
    for source in ALL_STATES:
        for target in ALL_STATES:
            assert can_transition(source, target) is (target in ALLOWED_TRANSITIONS[source])


def test_every_disallowed_transition_is_rejected() -> None:
    rejected = 0
    for source in ALL_STATES:
        for target in ALL_STATES:
            if target in ALLOWED_TRANSITIONS[source]:
                continue
            rejected += 1
            with pytest.raises(InvalidTransition):
                require_transition(source, target)
    assert rejected > 0


def test_every_allowed_transition_is_accepted() -> None:
    for source, targets in ALLOWED_TRANSITIONS.items():
        for target in targets:
            require_transition(source, target)


def test_finalized_is_the_only_terminal_state() -> None:
    assert frozenset({RunState.FINALIZED}) == FINAL_STATES
    assert ALLOWED_TRANSITIONS[RunState.FINALIZED] == frozenset()


def test_every_non_final_state_can_finalize() -> None:
    for state in ALL_STATES:
        if state is RunState.FINALIZED:
            continue
        assert can_transition(state, RunState.FINALIZED)


def test_no_state_can_leave_finalized() -> None:
    for target in ALL_STATES:
        assert not can_transition(RunState.FINALIZED, target)


def test_the_happy_path_is_the_documented_order() -> None:
    for source, target in zip(HAPPY_PATH, HAPPY_PATH[1:], strict=False):
        assert can_transition(source, target), f"{source} -> {target}"


def test_a_finalized_record_is_marked_finalized() -> None:
    record = RunRecord(
        run_id="run-1",
        trigger_id="trigger-1",
        automation=AutomationId("demo"),
        item_id="item-1",
        sequence=1,
        state=RunState.FINALIZED,
        finalization=Finalization.PUBLISHED,
        detail="",
        history=(RunState.RECEIVED, RunState.FINALIZED),
    )

    assert record.finalized

    in_flight = replace(record, state=RunState.EXECUTING, finalization=None)
    assert not in_flight.finalized


def test_every_named_outcome_exists() -> None:
    assert {outcome.value for outcome in Finalization} == {
        "published",
        "stale",
        "superseded",
        "denied",
        "failed",
        "lease-lost",
    }
