"""The result-artifact contract: versioned, serializable and vendor-neutral."""

from __future__ import annotations

import json
from typing import Any

import pytest

from greenhouses.core.domain.artifact import Artifact
from greenhouses.core.domain.errors import InvalidResult, UnknownArtifactVersion
from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.work_item import Revision

VENDOR_MARKERS = ("http", "://", "authorization", "accept", "reply", "jira", "github")


def _artifact(**overrides: Any) -> Artifact:
    base: dict[str, Any] = {
        "version": "1",
        "automation": AutomationId("demo"),
        "item_id": "item-1",
        "revision": Revision("revision"),
        "payload": {"summary": "hello", "count": 2},
    }
    base.update(overrides)
    return Artifact(**base)


def test_round_trips_through_json() -> None:
    artifact = _artifact()

    restored = Artifact.from_json(artifact.to_json())

    assert restored == artifact
    assert restored.artifact_id == artifact.artifact_id


def test_identity_is_stable_and_content_addressed() -> None:
    artifact = _artifact()

    assert artifact.artifact_id == _artifact().artifact_id
    assert artifact.artifact_id != _artifact(payload={"summary": "different"}).artifact_id


def test_identity_is_derived_without_new_hashing() -> None:
    # Derived through compute_revision: a 64-character lowercase digest.
    artifact_id = _artifact().artifact_id
    assert len(artifact_id) == 64
    assert artifact_id == artifact_id.lower()


def test_an_unknown_version_is_rejected_by_validation() -> None:
    artifact = _artifact(version="99")

    with pytest.raises(UnknownArtifactVersion):
        artifact.validated()


def test_an_unknown_version_is_rejected_on_load() -> None:
    data = _artifact().to_dict()
    data["version"] = "99"
    with pytest.raises(UnknownArtifactVersion):
        Artifact.from_dict(data)

    with pytest.raises(UnknownArtifactVersion):
        Artifact.from_json(json.dumps(data))


@pytest.mark.parametrize("text", ["not json", "[]", '"a string"'])
def test_malformed_json_is_rejected(text: str) -> None:
    with pytest.raises(InvalidResult):
        Artifact.from_json(text)


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"version": 1},
        {"version": "1"},
        {"version": "1", "automation": "demo", "item_id": "item-1"},
        {"version": "1", "automation": "demo", "item_id": "item-1", "revision": "r"},
        {
            "version": "1",
            "automation": "demo",
            "item_id": "item-1",
            "revision": "r",
            "payload": [],
        },
    ],
)
def test_from_dict_rejects_an_incomplete_shape(data: dict[str, Any]) -> None:
    with pytest.raises(InvalidResult):
        Artifact.from_dict(data)


def test_a_non_serializable_payload_is_rejected() -> None:
    artifact = _artifact(payload={"bad": object()})

    with pytest.raises(InvalidResult):
        artifact.validated()


def test_a_missing_item_id_is_rejected() -> None:
    artifact = _artifact(item_id="")

    with pytest.raises(InvalidResult):
        artifact.validated()


def test_the_serialized_artifact_is_vendor_neutral() -> None:
    serialized = _artifact().to_json().lower()
    for marker in VENDOR_MARKERS:
        assert marker not in serialized


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_number_is_rejected(value: float) -> None:
    artifact = _artifact(payload={"number": value})

    with pytest.raises(InvalidResult):
        artifact.validated()


def test_a_non_object_payload_is_rejected() -> None:
    payload: Any = [1, 2]

    with pytest.raises(InvalidResult):
        _artifact(payload=payload)


def test_a_non_string_key_is_rejected() -> None:
    payload: Any = {1: "a"}
    artifact = _artifact(payload=payload)

    with pytest.raises(InvalidResult):
        artifact.validated()


def test_a_rejected_payload_cannot_collide_with_a_string_key() -> None:
    payload: Any = {1: "a", "1": "b"}
    artifact = _artifact(payload=payload)

    with pytest.raises(InvalidResult):
        artifact.validated()
