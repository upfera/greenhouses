"""A fully in-memory environment for one local run.

The operator entry point builds this environment and runs the flow with it. It
touches no network, no filesystem and no external service, and it wires the
synthetic role behind the executor port.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.secrets import Capability, SecretRef, SecretScope
from greenhouses.core.domain.work_item import WorkItem
from greenhouses.fakes.artifacts import InMemoryArtifactStore
from greenhouses.fakes.clock import ManualClock
from greenhouses.fakes.executor import InMemoryExecutor
from greenhouses.fakes.provider import InMemoryProvider
from greenhouses.fakes.secrets import InMemorySecretStore
from greenhouses.fakes.state import InMemoryLeaseStore, InMemoryRunStateStore
from greenhouses.roles.synthetic import SyntheticRole
from greenhouses.runtime.definition import AutomationDefinition
from greenhouses.runtime.dispatch import DeliveredEvent, Dispatcher
from greenhouses.runtime.service import RunService

DEFAULT_AUTOMATION = AutomationId("local-demo")
DEFAULT_ITEM_ID = "work-item-1"
DEFAULT_CAPABILITY = "summarize"
EXECUTION_SECRET_NAME = "execution-token"
CONTROL_PLANE_SECRET_NAME = "supervisor-token"
_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


def default_work_item(item_id: str = DEFAULT_ITEM_ID) -> WorkItem:
    """The representative work item the local flow acts on."""
    return WorkItem(
        item_id=item_id,
        title="Local demo work item",
        state="open",
        labels=("demo",),
        body="Exercise the local lifecycle.",
    )


@dataclass(frozen=True, slots=True)
class LocalEnvironment:
    """Every collaborator a local run needs, wired together."""

    service: RunService
    dispatcher: Dispatcher
    provider: InMemoryProvider
    artifacts: InMemoryArtifactStore
    secrets: InMemorySecretStore
    clock: ManualClock
    automation: AutomationId
    item_id: str

    def default_event(self) -> DeliveredEvent:
        return DeliveredEvent(
            event_id="event-1",
            automation=self.automation,
            item_id=self.item_id,
            sequence=1,
        )


def build_local_environment(
    *, automation: AutomationId = DEFAULT_AUTOMATION, item_id: str = DEFAULT_ITEM_ID
) -> LocalEnvironment:
    """Build an offline environment that can run the eleven-step flow."""
    provider = InMemoryProvider([default_work_item(item_id)])
    secrets = InMemorySecretStore(
        {
            SecretRef(EXECUTION_SECRET_NAME, SecretScope.EXECUTION): "demo-execution-value",
            SecretRef(
                CONTROL_PLANE_SECRET_NAME, SecretScope.CONTROL_PLANE
            ): "demo-supervisor-value",
        }
    )
    artifacts = InMemoryArtifactStore()
    clock = ManualClock(_EPOCH)
    role = SyntheticRole()
    definition = AutomationDefinition(
        automation=automation,
        role=role.name,
        capabilities=(Capability(DEFAULT_CAPABILITY, secret=EXECUTION_SECRET_NAME),),
    )
    service = RunService(
        automations={automation: definition},
        provider=provider,
        executor=InMemoryExecutor(role),
        runs=InMemoryRunStateStore(),
        leases=InMemoryLeaseStore(),
        secrets=secrets,
        artifacts=artifacts,
        clock=clock,
    )
    return LocalEnvironment(
        service=service,
        dispatcher=Dispatcher(service, provider),
        provider=provider,
        artifacts=artifacts,
        secrets=secrets,
        clock=clock,
        automation=automation,
        item_id=item_id,
    )
