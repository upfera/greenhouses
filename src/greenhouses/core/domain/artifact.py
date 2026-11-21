"""Versioned, serializable, vendor-neutral result artifacts.

An artifact is what a run produces and what a supervisor validates and
persists. It carries no provider SDK type, URL, header or status: only plain
JSON-compatible values and core identities. Its identity is derived through
``compute_revision``, never through fresh hashing code.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass

from greenhouses.core.domain.errors import InvalidResult, UnknownArtifactVersion
from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.revision import compute_revision
from greenhouses.core.domain.work_item import Revision

ARTIFACT_VERSION = "1"
SUPPORTED_ARTIFACT_VERSIONS = frozenset({ARTIFACT_VERSION})

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]


def _canonical_key(key: object) -> str:
    """Return the key as a string, or fail closed.

    Coercing silently would let ``{1: "a", "1": "b"}`` collapse into one key, changing the
    artifact's identity without anyone noticing.
    """
    if not isinstance(key, str):
        raise InvalidResult(f"an artifact payload may not use the {type(key).__name__} key {key!r}")
    return key


def _canonical(value: object) -> JsonValue:
    """Return ``value`` as plain JSON-compatible data, or fail closed."""
    if isinstance(value, float) and not math.isfinite(value):
        # Non-finite floats are not JSON: they serialize as bare NaN/Infinity tokens.
        raise InvalidResult(f"an artifact payload may not contain {value!r}")
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, Mapping):
        return {_canonical_key(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_canonical(item) for item in value]
    raise InvalidResult(f"an artifact payload may not contain {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class Artifact:
    """A run result."""

    version: str
    automation: AutomationId
    item_id: str
    revision: Revision
    payload: Mapping[str, JsonValue]

    def __post_init__(self) -> None:
        if not isinstance(self.payload, Mapping):
            raise InvalidResult(
                f"an artifact payload must be an object, not {type(self.payload).__name__}"
            )

    @property
    def artifact_id(self) -> str:
        """Return this artifact's content identity, derived by ``compute_revision``."""
        canonical = json.dumps(
            {
                "version": self.version,
                "automation": self.automation.name,
                "item_id": self.item_id,
                "revision": self.revision.value,
                "payload": _canonical(self.payload),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return compute_revision(self.version, "artifact", (self.automation.name,), canonical)

    def validated(self) -> Artifact:
        """Return this artifact, or fail closed on an unknown version or shape."""
        if self.version not in SUPPORTED_ARTIFACT_VERSIONS:
            raise UnknownArtifactVersion(f"unknown artifact version {self.version!r}")
        if not self.item_id:
            raise InvalidResult("an artifact needs an item id")
        _canonical(self.payload)
        return self

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "version": self.version,
            "automation": self.automation.name,
            "item_id": self.item_id,
            "revision": self.revision.value,
            "payload": _canonical(self.payload),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_dict(cls, data: Mapping[str, JsonValue]) -> Artifact:
        version = data.get("version")
        if not isinstance(version, str):
            raise InvalidResult("an artifact needs a version")
        if version not in SUPPORTED_ARTIFACT_VERSIONS:
            raise UnknownArtifactVersion(f"unknown artifact version {version!r}")
        automation = data.get("automation")
        item_id = data.get("item_id")
        revision = data.get("revision")
        payload = data.get("payload")
        if not isinstance(automation, str) or not isinstance(item_id, str):
            raise InvalidResult("an artifact needs an automation and an item id")
        if not isinstance(revision, str):
            raise InvalidResult("an artifact needs a revision")
        if not isinstance(payload, dict):
            raise InvalidResult("an artifact payload must be an object")
        return cls(
            version=version,
            automation=AutomationId(automation),
            item_id=item_id,
            revision=Revision(revision),
            payload=payload,
        )

    @classmethod
    def from_json(cls, text: str) -> Artifact:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise InvalidResult(f"an artifact must be valid JSON: {error.msg}") from error
        if not isinstance(data, dict):
            raise InvalidResult("an artifact must be a JSON object")
        return cls.from_dict(data)
