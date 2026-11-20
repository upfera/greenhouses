"""The security invariants, proven through observable access and results."""

from __future__ import annotations

from collections.abc import Mapping

from support import (
    CAPABILITY,
    CONTROL_PLANE_SECRET,
    CONTROL_PLANE_SECRET_VALUE,
    EXECUTION_SECRET,
    EXECUTION_SECRET_VALUE,
    Harness,
    MutatingProvider,
    build_harness,
    default_definition,
    default_item,
    deliver,
    moved_item,
)

from greenhouses.core.domain.artifact import Artifact, JsonValue
from greenhouses.core.domain.errors import SecretAccessDenied
from greenhouses.core.domain.execution import ExecutionRequest
from greenhouses.core.domain.lifecycle import Finalization
from greenhouses.core.ports.roles import Role
from greenhouses.core.ports.secrets import SecretStore
from greenhouses.roles.synthetic import SyntheticRole


class ControlPlaneProbeRole:
    """Tries to read a control-plane secret and records the denial."""

    name = "control-plane-probe"

    def __init__(self) -> None:
        self.denied: SecretAccessDenied | None = None

    def produce(self, request: ExecutionRequest) -> Mapping[str, JsonValue]:
        try:
            request.secrets.read_reference(CONTROL_PLANE_SECRET)
        except SecretAccessDenied as error:
            self.denied = error
            raise
        raise AssertionError("a control-plane secret was reachable from an execution")


class UngrantedCapabilityRole:
    """Tries to read a capability that no grant declares, and records the denial."""

    name = "ungranted"

    def __init__(self) -> None:
        self.denied: SecretAccessDenied | None = None

    def produce(self, request: ExecutionRequest) -> Mapping[str, JsonValue]:
        try:
            request.secrets.read("not-granted")
        except SecretAccessDenied as error:
            self.denied = error
            raise
        raise AssertionError("an ungranted capability was reachable from an execution")


def _published_artifacts(harness: Harness) -> list[Artifact]:
    loaded = [
        harness.artifacts.load(publication.artifact_id)
        for publication in harness.provider.publications
    ]
    return [artifact for artifact in loaded if artifact is not None]


def test_a_granted_execution_secret_is_reachable_through_its_grant() -> None:
    harness = build_harness()

    record = deliver(harness)

    assert record.finalization is Finalization.PUBLISHED
    artifact = _published_artifacts(harness)[-1]
    assert artifact.payload["capabilities"] == [
        {"capability": CAPABILITY, "secret": EXECUTION_SECRET.name, "resolved": True}
    ]


def test_a_control_plane_secret_is_unreachable_from_an_execution() -> None:
    role = ControlPlaneProbeRole()
    harness = build_harness(role=role, definition=default_definition(role=role.name))

    record = deliver(harness)

    assert role.denied is not None
    assert CONTROL_PLANE_SECRET_VALUE not in str(role.denied)
    assert record.finalization is Finalization.FAILED
    assert harness.provider.publications == []


def test_an_ungranted_capability_fails_closed() -> None:
    role = UngrantedCapabilityRole()
    harness = build_harness(role=role, definition=default_definition(role=role.name))

    record = deliver(harness)

    assert role.denied is not None
    assert record.finalization is Finalization.FAILED
    assert harness.provider.publications == []


def test_no_secret_value_reaches_artifacts_state_or_errors() -> None:
    harness = build_harness()

    record = deliver(harness)

    artifact = _published_artifacts(harness)[-1].to_json()
    for value in (EXECUTION_SECRET_VALUE, CONTROL_PLANE_SECRET_VALUE):
        assert value not in artifact
        assert value not in record.detail
        assert value not in repr(record)


def test_publication_happens_only_after_validation() -> None:
    provider = MutatingProvider([default_item()], moved_item(), after_read=2)
    harness = build_harness(provider=provider)

    record = deliver(harness)

    assert record.finalization is Finalization.STALE
    assert harness.provider.publications == []


def test_a_role_cannot_publish() -> None:
    assert not hasattr(SyntheticRole(), "publish")
    assert "publish" not in set(dir(Role))


def test_state_is_not_a_secret_store() -> None:
    harness = build_harness()

    record = deliver(harness)

    # The run-state store resolves no secret: it is a different abstraction.
    assert not isinstance(harness.runs, SecretStore)
    for rendered in (record.detail, record.item_id, repr(record), repr(record.history)):
        assert EXECUTION_SECRET_VALUE not in rendered
        assert CONTROL_PLANE_SECRET_VALUE not in rendered
