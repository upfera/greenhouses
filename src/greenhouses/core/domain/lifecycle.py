"""The run lifecycle: states, allowed transitions and terminal outcomes.

The lifecycle has eleven ordered steps and a single terminal state. Every path,
including every failure, ends in ``FINALIZED`` with a ``Finalization`` naming
the outcome. Transitions are a closed set; anything else raises
``InvalidTransition``.

    received -> resolved -> configured -> prepared -> leased -> granted
        -> executing -> artifact-persisted -> validated -> published -> finalized

``FINALIZED`` is reachable from every state, so any step can end the run with a
defined outcome and release its lease. ``FINALIZED`` has no outgoing transition:
a finalized run is never re-entered, which makes duplicate delivery a read
rather than a second run.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from greenhouses.core.domain.errors import InvalidTransition
from greenhouses.core.domain.identity import AutomationId


class RunState(StrEnum):
    """A state in the run lifecycle, in the order the steps run."""

    RECEIVED = "received"
    RESOLVED = "resolved"
    CONFIGURED = "configured"
    PREPARED = "prepared"
    LEASED = "leased"
    GRANTED = "granted"
    EXECUTING = "executing"
    ARTIFACT_PERSISTED = "artifact-persisted"
    VALIDATED = "validated"
    PUBLISHED = "published"
    FINALIZED = "finalized"


class Finalization(StrEnum):
    """The terminal outcome recorded when a run reaches ``FINALIZED``."""

    PUBLISHED = "published"
    STALE = "stale"
    SUPERSEDED = "superseded"
    DENIED = "denied"
    FAILED = "failed"
    LEASE_LOST = "lease-lost"


ALLOWED_TRANSITIONS: Mapping[RunState, frozenset[RunState]] = MappingProxyType(
    {
        RunState.RECEIVED: frozenset({RunState.RESOLVED, RunState.FINALIZED}),
        RunState.RESOLVED: frozenset({RunState.CONFIGURED, RunState.FINALIZED}),
        RunState.CONFIGURED: frozenset({RunState.PREPARED, RunState.FINALIZED}),
        RunState.PREPARED: frozenset({RunState.LEASED, RunState.FINALIZED}),
        RunState.LEASED: frozenset({RunState.GRANTED, RunState.FINALIZED}),
        RunState.GRANTED: frozenset({RunState.EXECUTING, RunState.FINALIZED}),
        RunState.EXECUTING: frozenset({RunState.ARTIFACT_PERSISTED, RunState.FINALIZED}),
        RunState.ARTIFACT_PERSISTED: frozenset({RunState.VALIDATED, RunState.FINALIZED}),
        RunState.VALIDATED: frozenset({RunState.PUBLISHED, RunState.FINALIZED}),
        RunState.PUBLISHED: frozenset({RunState.FINALIZED}),
        RunState.FINALIZED: frozenset(),
    }
)

FINAL_STATES: frozenset[RunState] = frozenset({RunState.FINALIZED})


def can_transition(source: RunState, target: RunState) -> bool:
    """Return whether the state machine allows ``source -> target``."""
    return target in ALLOWED_TRANSITIONS[source]


def require_transition(source: RunState, target: RunState) -> None:
    """Raise ``InvalidTransition`` unless ``source -> target`` is allowed."""
    if not can_transition(source, target):
        raise InvalidTransition(f"{source.value} -> {target.value} is not an allowed transition")


@dataclass(frozen=True, slots=True)
class RunRecord:
    """The observable state of one run."""

    run_id: str
    trigger_id: str
    automation: AutomationId
    item_id: str
    sequence: int
    state: RunState
    finalization: Finalization | None
    detail: str
    history: tuple[RunState, ...]

    @property
    def finalized(self) -> bool:
        return self.state in FINAL_STATES
