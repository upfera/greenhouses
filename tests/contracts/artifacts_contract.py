"""Reusable contract suite for ``ArtifactStore``.

An adapter runs this suite unchanged by subclassing ``ArtifactStoreContract``
and supplying a ``store`` fixture.
"""

from __future__ import annotations

import pytest

from greenhouses.core.domain.artifact import Artifact
from greenhouses.core.domain.errors import UnknownArtifactVersion
from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.work_item import Revision
from greenhouses.core.ports.artifacts import ArtifactStore


def contract_artifact(version: str = "1") -> Artifact:
    return Artifact(
        version=version,
        automation=AutomationId("contract"),
        item_id="contract-item",
        revision=Revision("revision"),
        payload={"ok": True},
    )


class ArtifactStoreContract:
    """Behaviours every artifact-store adapter must have."""

    @pytest.fixture
    def store(self) -> ArtifactStore:
        raise NotImplementedError("an artifact adapter must supply its implementation")

    def test_save_returns_an_identity_that_loads_back(self, store: ArtifactStore) -> None:
        artifact = contract_artifact()
        artifact_id = store.save(artifact)

        assert artifact_id == artifact.artifact_id
        assert store.load(artifact_id) == artifact

    def test_loading_an_absent_artifact_is_none(self, store: ArtifactStore) -> None:
        assert store.load("absent-artifact") is None

    def test_an_unknown_version_fails_closed(self, store: ArtifactStore) -> None:
        artifact = contract_artifact(version="99")

        with pytest.raises(UnknownArtifactVersion):
            store.save(artifact)
