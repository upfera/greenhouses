"""Ports the core flow consumes, each with a real call site.

Every port here is used by the runtime flow or by a test that drives it. There
are no speculative ports.
"""

from __future__ import annotations

from greenhouses.core.ports.artifacts import ArtifactStore
from greenhouses.core.ports.clock import Clock
from greenhouses.core.ports.executor import Executor
from greenhouses.core.ports.provider import WorkItemProvider
from greenhouses.core.ports.roles import Role
from greenhouses.core.ports.secrets import SecretStore
from greenhouses.core.ports.state import Lease, LeaseStore, RunStateStore

__all__ = [
    "ArtifactStore",
    "Clock",
    "Executor",
    "Lease",
    "LeaseStore",
    "Role",
    "RunStateStore",
    "SecretStore",
    "WorkItemProvider",
]
