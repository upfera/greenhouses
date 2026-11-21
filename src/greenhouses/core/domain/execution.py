"""What a run hands to an executor, and what an executor returns.

The executor is a long-running execution model: ``start`` returns an execution
id, ``poll`` reports its state, ``result`` yields its output and ``stop`` ends
it. A synchronous adapter implements this over a single call; a real executor
maps it onto its own lifecycle without changing the contract.

No secret value crosses this boundary: an executor receives ``GrantedSecrets``,
which resolves only what a run-scoped grant allows.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from greenhouses.core.domain.artifact import JsonValue
from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.secrets import GrantedSecrets
from greenhouses.core.domain.work_item import Revision


@dataclass(frozen=True, slots=True)
class InputSnapshot:
    """The work-item content a run acts on, frozen when the run starts."""

    item_id: str
    revision: Revision
    fields: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """Everything an executor needs, and nothing it does not."""

    run_id: str
    automation: AutomationId
    role: str
    snapshot: InputSnapshot
    secrets: GrantedSecrets
    parameters: Mapping[str, str] = field(default_factory=dict)


class ExecutionState(StrEnum):
    """The state of a single execution."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class ExecutionOutput:
    """An execution's result payload, bound to the work item it was produced for."""

    item_id: str
    payload: Mapping[str, JsonValue]
    detail: str = ""
