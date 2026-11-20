"""One synthetic representative role.

It is the smallest role that exercises the whole lifecycle: it reads the work
item it was given, resolves only the execution secrets its run-scoped grants
allow, and returns a vendor-neutral payload. It never publishes and never sees
a control-plane secret.
"""

from __future__ import annotations

from collections.abc import Mapping

from greenhouses.core.domain.artifact import JsonValue
from greenhouses.core.domain.execution import ExecutionRequest


class SyntheticRole:
    """A representative role that produces a summary of its work item."""

    name = "synthetic"

    def produce(self, request: ExecutionRequest) -> Mapping[str, JsonValue]:
        accesses: list[JsonValue] = []
        for grant in request.secrets.grants:
            secret = request.secrets.read(grant.capability)
            entry: dict[str, JsonValue] = {
                "capability": grant.capability,
                "secret": secret.reference.name,
                "resolved": True,
            }
            accesses.append(entry)
        summary = "; ".join(
            f"{key}={value}" for key, value in sorted(request.snapshot.fields.items())
        )
        payload: dict[str, JsonValue] = {
            "role": self.name,
            "item_id": request.snapshot.item_id,
            "revision": request.snapshot.revision.value,
            "summary": summary,
            "capabilities": accesses,
        }
        return payload
