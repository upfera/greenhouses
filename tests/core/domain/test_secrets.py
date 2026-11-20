"""Run-scoped grants and the access they do and do not unlock."""

from __future__ import annotations

import pytest

from greenhouses.core.domain.errors import InvalidGrant, SecretAccessDenied
from greenhouses.core.domain.secrets import (
    Capability,
    GrantedSecrets,
    SecretRef,
    SecretScope,
    SecretValue,
    issue_grants,
)
from greenhouses.fakes.secrets import InMemorySecretStore

EXECUTION = SecretRef("execution-secret", SecretScope.EXECUTION)
CONTROL_PLANE = SecretRef("supervisor-secret", SecretScope.CONTROL_PLANE)
STORE = InMemorySecretStore(
    {
        EXECUTION: "execution-value",
        CONTROL_PLANE: "supervisor-value",
    }
)


def test_issue_grants_binds_each_capability_to_the_run() -> None:
    grants = issue_grants("run-1", (Capability("summarize", secret="execution-secret"),))

    assert len(grants) == 1
    assert grants[0].run_id == "run-1"
    assert grants[0].capability == "summarize"
    assert grants[0].secret == EXECUTION


def test_issue_grants_rejects_an_unsupported_scope() -> None:
    capability = Capability(
        "summarize", secret="supervisor-secret", scope=SecretScope.CONTROL_PLANE
    )

    with pytest.raises(InvalidGrant):
        issue_grants("run-1", (capability,))


def test_issue_grants_rejects_an_unnamed_capability() -> None:
    capability = Capability("")

    with pytest.raises(InvalidGrant):
        issue_grants("run-1", (capability,))


def test_a_granted_capability_resolves_its_secret() -> None:
    grants = issue_grants("run-1", (Capability("summarize", secret="execution-secret"),))
    access = GrantedSecrets(run_id="run-1", grants=grants, store=STORE)

    assert access.read("summarize").value == "execution-value"


def test_an_ungranted_capability_is_denied() -> None:
    access = GrantedSecrets(run_id="run-1", grants=(), store=STORE)

    with pytest.raises(SecretAccessDenied):
        access.read("summarize")


def test_a_grant_from_another_run_does_not_unlock() -> None:
    grants = issue_grants("run-1", (Capability("summarize", secret="execution-secret"),))
    access = GrantedSecrets(run_id="run-2", grants=grants, store=STORE)

    with pytest.raises(SecretAccessDenied):
        access.read("summarize")


def test_a_control_plane_secret_is_unreachable_by_reference() -> None:
    access = GrantedSecrets(run_id="run-1", grants=(), store=STORE)

    with pytest.raises(SecretAccessDenied) as error:
        access.read_reference(CONTROL_PLANE)

    assert "supervisor-value" not in str(error.value)


def test_a_granted_execution_reference_resolves() -> None:
    grants = issue_grants("run-1", (Capability("summarize", secret="execution-secret"),))
    access = GrantedSecrets(run_id="run-1", grants=grants, store=STORE)

    assert access.read_reference(EXECUTION).value == "execution-value"


def test_an_ungranted_reference_is_denied() -> None:
    access = GrantedSecrets(run_id="run-1", grants=(), store=STORE)

    with pytest.raises(SecretAccessDenied):
        access.read_reference(EXECUTION)


def test_a_secret_value_never_renders_itself() -> None:
    value = SecretValue(reference=EXECUTION, value="execution-value")

    assert "execution-value" not in repr(value)
    assert "execution-value" not in str(value)
    assert value.reference == EXECUTION
