"""What the runtime resolves an automation identity to.

A definition is the runtime's view of one automation: the role it runs, the
versioned configuration it loads, the capabilities it may be granted, and the
parameters it passes to an execution. A versioned manifest system and closed
configuration schemas are later work; this is the minimal shape the flow needs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from greenhouses.core.domain.configuration import Configuration, ExecutionPolicy
from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.secrets import Capability


@dataclass(frozen=True, slots=True)
class AutomationDefinition:
    """The runtime's definition of one automation."""

    automation: AutomationId
    role: str
    configuration_version: str = "1"
    capabilities: tuple[Capability, ...] = ()
    parameters: Mapping[str, str] = field(default_factory=dict)
    lease_ttl_seconds: int = 60

    def configuration(self) -> Configuration:
        """Build the versioned configuration this definition implies."""
        return Configuration(
            automation=self.automation,
            version=self.configuration_version,
            role=self.role,
            policy=ExecutionPolicy(
                capabilities=self.capabilities,
                lease_ttl_seconds=self.lease_ttl_seconds,
            ),
        )
