"""Versioned configuration and the execution policy it carries.

This is deliberately minimal: a version, the automation it configures, the
role it runs, and the policy of declared capabilities and lease duration. A
closed configuration schema is later work.
"""

from __future__ import annotations

from dataclasses import dataclass

from greenhouses.core.domain.errors import InvalidConfiguration
from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.secrets import Capability

SUPPORTED_CONFIGURATION_VERSIONS = frozenset({"1"})


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    """What a run is allowed to do: declared capabilities and its lease length."""

    capabilities: tuple[Capability, ...] = ()
    lease_ttl_seconds: int = 60


@dataclass(frozen=True, slots=True)
class Configuration:
    """A versioned configuration for one automation."""

    automation: AutomationId
    version: str
    role: str
    policy: ExecutionPolicy

    def validated(self) -> Configuration:
        """Return this configuration, or fail closed with ``InvalidConfiguration``."""
        if self.version not in SUPPORTED_CONFIGURATION_VERSIONS:
            raise InvalidConfiguration(f"unsupported configuration version {self.version!r}")
        if not self.role:
            raise InvalidConfiguration("a configuration needs a role")
        if self.policy.lease_ttl_seconds <= 0:
            raise InvalidConfiguration("the lease duration must be positive")
        return self
