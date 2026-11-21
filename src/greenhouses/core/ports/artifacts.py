"""The result-artifact port.

Artifacts are persisted and read back by identity. An implementation validates
the artifact it is given, so an unknown version fails closed at the boundary.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from greenhouses.core.domain.artifact import Artifact


@runtime_checkable
class ArtifactStore(Protocol):
    """Persists versioned result artifacts."""

    def save(self, artifact: Artifact) -> str:
        """Validate and persist an artifact, returning its identity."""
        ...

    def load(self, artifact_id: str) -> Artifact | None:
        """Return a persisted artifact, or ``None`` when it is absent."""
        ...
