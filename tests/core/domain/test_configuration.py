"""Configuration resolution and validation."""

from __future__ import annotations

import pytest

from greenhouses.core.domain.configuration import (
    SUPPORTED_CONFIGURATION_VERSIONS,
    Configuration,
    ExecutionPolicy,
)
from greenhouses.core.domain.errors import InvalidConfiguration
from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.secrets import Capability


def _configuration(**overrides: object) -> Configuration:
    values: dict[str, object] = {
        "version": "1",
        "automation": AutomationId("demo"),
        "role": "synthetic",
        "policy": ExecutionPolicy(lease_ttl_seconds=60),
    }
    values.update(overrides)
    return Configuration(**values)  # type: ignore[arg-type]


def test_a_well_formed_configuration_validates() -> None:
    assert _configuration().validated().version in SUPPORTED_CONFIGURATION_VERSIONS


def test_an_unsupported_version_fails_closed() -> None:
    configuration = _configuration(version="99")

    with pytest.raises(InvalidConfiguration):
        configuration.validated()


def test_a_configuration_without_a_role_fails_closed() -> None:
    configuration = _configuration(role="")

    with pytest.raises(InvalidConfiguration):
        configuration.validated()


@pytest.mark.parametrize("ttl", [0, -1])
def test_a_non_positive_lease_duration_fails_closed(ttl: int) -> None:
    policy = ExecutionPolicy(lease_ttl_seconds=ttl)
    configuration = _configuration(policy=policy)

    with pytest.raises(InvalidConfiguration):
        configuration.validated()


def test_a_policy_carries_its_capabilities() -> None:
    policy = ExecutionPolicy(
        lease_ttl_seconds=60,
        capabilities=(Capability("summarize", secret="execution-token"),),
    )

    assert [capability.name for capability in policy.capabilities] == ["summarize"]
