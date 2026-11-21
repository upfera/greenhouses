"""Domain errors shared by the core contracts.

Every error names what failed. None carries a secret value: a failure message
is part of the observable state, and secret values are never observable.
"""

from __future__ import annotations


class GreenhousesError(Exception):
    """Base class for failures raised across the core contracts."""


class InvalidTransition(GreenhousesError):
    """A lifecycle transition that the state machine does not allow."""


class InvalidConfiguration(GreenhousesError):
    """A configuration that fails validation, such as an unknown version."""


class InvalidGrant(GreenhousesError):
    """A capability grant that is undeclared, mis-scoped or malformed."""


class SecretAccessDenied(GreenhousesError):
    """A secret read that no run-scoped grant allows."""


class UnknownArtifactVersion(GreenhousesError):
    """An artifact whose version this build does not support."""


class InvalidResult(GreenhousesError):
    """A result that does not satisfy the artifact or work-item contract."""


class UnknownAutomation(GreenhousesError):
    """An automation identity that the catalogue does not resolve."""


class WorkItemNotFound(GreenhousesError):
    """A work item that the provider does not have."""


class LeaseUnavailable(GreenhousesError):
    """A lease that another live holder owns."""


class LeaseLost(GreenhousesError):
    """A lease that expired or was taken over before a run could publish."""


class ExecutionFailed(GreenhousesError):
    """An executor that ended without a usable result."""


class StaleWorkItem(GreenhousesError):
    """A publication attempted against a work item whose revision moved."""
