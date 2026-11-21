"""The role contract.

A role produces a result payload from the work item it is given. It never
publishes: publication is a runtime operation performed through the trusted
provider boundary. The protocol is the seam a real executor adapter drives.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from greenhouses.core.domain.artifact import JsonValue
from greenhouses.core.domain.execution import ExecutionRequest


@runtime_checkable
class Role(Protocol):
    """Produces a result payload for one work item."""

    name: str

    def produce(self, request: ExecutionRequest) -> Mapping[str, JsonValue]:
        """Return the result payload, using only the request's granted secrets."""
        ...
