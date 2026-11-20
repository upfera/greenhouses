"""Identity of an automation.

An identity is a name and nothing else: provider, executor and catalogue
specifics live outside core.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class AutomationId:
    """Stable identity of an automation."""

    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("an automation identity needs a non-empty name")
