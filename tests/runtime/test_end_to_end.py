"""The eleven-step flow, driven through the operator entry point.

The only way this test reaches the flow is ``greenhouses.cli.main``: no test
here calls a fake or the runtime service directly. Nothing on the path touches
the network, and the suite's autouse guard would fail it if anything tried.
"""

from __future__ import annotations

import json
from typing import Any

from greenhouses.cli import main
from greenhouses.core.domain.artifact import SUPPORTED_ARTIFACT_VERSIONS, Artifact

EXPECTED_STATES = [
    "received",
    "resolved",
    "configured",
    "prepared",
    "leased",
    "granted",
    "executing",
    "artifact-persisted",
    "validated",
    "published",
    "finalized",
]

# The values seeded by the local environment. Neither may appear in the output.
EXECUTION_SECRET_VALUE = "demo-execution-value"
CONTROL_PLANE_SECRET_VALUE = "demo-supervisor-value"


def _run(capsys: Any, *args: str) -> dict[str, Any]:
    assert main(["run", *args]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def test_the_operator_entry_point_runs_all_eleven_steps(capsys: Any) -> None:
    summary = _run(capsys, "--item", "e2e-item")

    assert summary["states"] == EXPECTED_STATES
    assert summary["finalization"] == "published"
    assert summary["published"] is True
    assert summary["item_id"] == "e2e-item"


def test_the_published_artifact_round_trips(capsys: Any) -> None:
    summary = _run(capsys, "--item", "e2e-item")

    artifact = Artifact.from_dict(summary["artifact"])

    assert artifact.version in SUPPORTED_ARTIFACT_VERSIONS
    assert artifact.artifact_id == summary["artifact_id"]
    assert artifact.item_id == "e2e-item"
    assert artifact.to_json() == json.dumps(
        summary["artifact"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def test_the_granted_capability_is_exercised(capsys: Any) -> None:
    summary = _run(capsys)

    capabilities = summary["artifact"]["payload"]["capabilities"]

    assert capabilities == [
        {"capability": "summarize", "secret": "execution-token", "resolved": True}
    ]


def test_no_secret_value_reaches_the_output(capsys: Any) -> None:
    summary = _run(capsys)

    text = json.dumps(summary)

    assert EXECUTION_SECRET_VALUE not in text
    assert CONTROL_PLANE_SECRET_VALUE not in text


def test_the_run_is_repeatable_and_offline(capsys: Any) -> None:
    first = _run(capsys)
    second = _run(capsys)

    assert first["states"] == second["states"]
    assert first["finalization"] == second["finalization"]
