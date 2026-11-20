"""The privileged publication request and its receipt.

Publication is a trusted-boundary operation: an execution describes what it
wants published, and only the provider acts. The request names the revision the
result was validated against, so a provider can reject a publication against a
moved work item.
"""

from __future__ import annotations

from dataclasses import dataclass

from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.work_item import Revision


@dataclass(frozen=True, slots=True)
class Publication:
    """A request to publish a validated result through the trusted boundary."""

    automation: AutomationId
    item_id: str
    expected_revision: Revision
    artifact_id: str
    summary: str


@dataclass(frozen=True, slots=True)
class PublicationReceipt:
    """What the provider recorded for a publication."""

    item_id: str
    revision: Revision
    artifact_id: str
