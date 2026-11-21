"""An in-memory artifact store."""

from __future__ import annotations

from greenhouses.core.domain.artifact import Artifact


class InMemoryArtifactStore:
    """Persists artifacts by identity and validates them on the way in."""

    def __init__(self) -> None:
        self._artifacts: dict[str, Artifact] = {}

    def save(self, artifact: Artifact) -> str:
        validated = artifact.validated()
        artifact_id = validated.artifact_id
        self._artifacts[artifact_id] = validated
        return artifact_id

    def load(self, artifact_id: str) -> Artifact | None:
        return self._artifacts.get(artifact_id)
