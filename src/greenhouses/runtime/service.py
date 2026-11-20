"""The run service: the eleven-step lifecycle in one place.

    receive trigger -> resolve automation and role -> load and validate config
    -> resolve snapshot and policy -> acquire lease -> issue grants
    -> invoke executor -> persist artifact -> re-read and validate
    -> publish -> persist final state and release lease

Every failure path funnels through ``_finalize`` (step 11) and the ``finally``
block releases the lease, so no run leaves a lease held.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import timedelta

from greenhouses.core.domain.artifact import ARTIFACT_VERSION, Artifact
from greenhouses.core.domain.configuration import Configuration
from greenhouses.core.domain.errors import (
    ExecutionFailed,
    GreenhousesError,
    InvalidGrant,
    InvalidResult,
    LeaseLost,
    LeaseUnavailable,
    SecretAccessDenied,
    StaleWorkItem,
    UnknownAutomation,
    WorkItemNotFound,
)
from greenhouses.core.domain.execution import (
    ExecutionOutput,
    ExecutionRequest,
    ExecutionState,
    InputSnapshot,
)
from greenhouses.core.domain.identity import AutomationId
from greenhouses.core.domain.lifecycle import (
    Finalization,
    RunRecord,
    RunState,
    require_transition,
)
from greenhouses.core.domain.publication import Publication
from greenhouses.core.domain.secrets import GrantedSecrets, issue_grants
from greenhouses.core.domain.trigger import Trigger
from greenhouses.core.ports.artifacts import ArtifactStore
from greenhouses.core.ports.clock import Clock
from greenhouses.core.ports.executor import Executor
from greenhouses.core.ports.provider import WorkItemProvider
from greenhouses.core.ports.secrets import SecretStore
from greenhouses.core.ports.state import Lease, LeaseStore, RunStateStore
from greenhouses.runtime.definition import AutomationDefinition

_MAX_POLLS = 1000

# Errors map to the finalization they produce. Anything not listed is a plain
# failure. ``LeaseLost`` and ``StaleWorkItem`` are distinct outcomes because a
# run that lost its lease or found a moved work item did not fail: it declined.
_ERROR_OUTCOMES: tuple[tuple[type[GreenhousesError], Finalization], ...] = (
    (LeaseLost, Finalization.LEASE_LOST),
    (StaleWorkItem, Finalization.STALE),
    (LeaseUnavailable, Finalization.DENIED),
    (InvalidGrant, Finalization.DENIED),
    (SecretAccessDenied, Finalization.DENIED),
)


def _outcome_for(error: GreenhousesError) -> Finalization:
    for error_type, outcome in _ERROR_OUTCOMES:
        if isinstance(error, error_type):
            return outcome
    return Finalization.FAILED


class RunService:
    """Drives one trigger through the lifecycle, using only its ports."""

    def __init__(
        self,
        *,
        automations: Mapping[AutomationId, AutomationDefinition],
        provider: WorkItemProvider,
        executor: Executor,
        runs: RunStateStore,
        leases: LeaseStore,
        secrets: SecretStore,
        artifacts: ArtifactStore,
        clock: Clock,
    ) -> None:
        self._automations = dict(automations)
        self._provider = provider
        self._executor = executor
        self._runs = runs
        self._leases = leases
        self._secrets = secrets
        self._artifacts = artifacts
        self._clock = clock

    def run(self, trigger: Trigger) -> RunRecord:
        """Run a normalized trigger and return its record.

        A duplicate delivery returns the recorded outcome without re-running;
        an older trigger than the last finalized one is recorded as superseded
        and does not run.
        """
        recorded = self._runs.get(trigger.trigger_id)
        if recorded is not None:
            return recorded
        if trigger.sequence <= self._runs.last_sequence(trigger.item_id):
            superseded = self._finalize(
                self._begin(trigger),
                Finalization.SUPERSEDED,
                "an older trigger arrived after a newer one completed",
            )
            return superseded

        record = self._begin(trigger)
        lease: Lease | None = None
        try:
            record, definition = self._resolve(record, trigger)
            record, configuration = self._configure(record, definition)
            record, snapshot = self._prepare(record, trigger)
            record, lease = self._acquire(record, trigger, configuration)
            record, request = self._grant(record, trigger, configuration, snapshot)
            record, output = self._execute(record, request)
            record, artifact = self._persist(record, trigger, output, snapshot)
            record = self._validate(record, trigger, artifact)
            record = self._publish(record, trigger, artifact, lease)
            return self._finalize(record, Finalization.PUBLISHED, "published")
        except GreenhousesError as error:
            return self._finalize(record, _outcome_for(error), str(error))
        except Exception as error:  # noqa: BLE001 - a trust boundary fails closed
            # An executor or port is a boundary: an unexpected error is a failed
            # run, not a crash. The message is omitted so nothing it carries,
            # including a secret, can reach the recorded state.
            return self._finalize(record, Finalization.FAILED, f"unexpected {type(error).__name__}")
        finally:
            if lease is not None:
                self._leases.release(lease)

    # 2. Resolve the automation and the role.
    def _resolve(
        self, record: RunRecord, trigger: Trigger
    ) -> tuple[RunRecord, AutomationDefinition]:
        definition = self._automations.get(trigger.automation)
        if definition is None:
            raise UnknownAutomation(f"no automation named {trigger.automation.name!r}")
        return self._advance(record, RunState.RESOLVED), definition

    # 3. Load and validate versioned configuration.
    def _configure(
        self, record: RunRecord, definition: AutomationDefinition
    ) -> tuple[RunRecord, Configuration]:
        configuration = definition.configuration().validated()
        return self._advance(record, RunState.CONFIGURED), configuration

    # 4. Resolve the input snapshot and the execution policy.
    def _prepare(self, record: RunRecord, trigger: Trigger) -> tuple[RunRecord, InputSnapshot]:
        item = self._provider.read(trigger.item_id)
        if item is None:
            raise WorkItemNotFound(f"no work item {trigger.item_id!r}")
        fields = {"title": item.title, "state": item.state, "body": item.body}
        snapshot = InputSnapshot(
            item_id=item.item_id,
            revision=item.revision,
            fields=fields,
        )
        return self._advance(record, RunState.PREPARED), snapshot

    # 5. Acquire the required state or lease.
    def _acquire(
        self, record: RunRecord, trigger: Trigger, configuration: Configuration
    ) -> tuple[RunRecord, Lease]:
        ttl = timedelta(seconds=configuration.policy.lease_ttl_seconds)
        lease = self._leases.acquire(trigger.item_id, record.run_id, ttl, self._clock.now())
        if lease is None:
            raise LeaseUnavailable(f"another run holds the lease for {trigger.item_id!r}")
        return self._advance(record, RunState.LEASED), lease

    # 6. Grant only the declared, execution-scoped capabilities.
    def _grant(
        self,
        record: RunRecord,
        trigger: Trigger,
        configuration: Configuration,
        snapshot: InputSnapshot,
    ) -> tuple[RunRecord, ExecutionRequest]:
        grants = issue_grants(record.run_id, configuration.policy.capabilities)
        request = ExecutionRequest(
            run_id=record.run_id,
            automation=trigger.automation,
            role=configuration.role,
            snapshot=snapshot,
            secrets=GrantedSecrets(run_id=record.run_id, grants=grants, store=self._secrets),
            parameters=dict(trigger.parameters),
        )
        return self._advance(record, RunState.GRANTED), request

    # 7. Invoke an executor.
    def _execute(
        self, record: RunRecord, request: ExecutionRequest
    ) -> tuple[RunRecord, ExecutionOutput]:
        record = self._advance(record, RunState.EXECUTING)
        return record, self._invoke(request)

    def _invoke(self, request: ExecutionRequest) -> ExecutionOutput:
        execution_id = self._executor.start(request)
        for _ in range(_MAX_POLLS):
            state = self._executor.poll(execution_id)
            if state is ExecutionState.SUCCEEDED:
                return self._executor.result(execution_id)
            if state in {ExecutionState.FAILED, ExecutionState.STOPPED}:
                raise ExecutionFailed(f"the executor ended in the {state.value!r} state")
        self._executor.stop(execution_id)
        raise ExecutionFailed("the executor did not finish within the poll budget")

    # 8. Validate and persist a versioned, serializable result artifact.
    def _persist(
        self,
        record: RunRecord,
        trigger: Trigger,
        output: ExecutionOutput,
        snapshot: InputSnapshot,
    ) -> tuple[RunRecord, Artifact]:
        if output.item_id != trigger.item_id:
            raise InvalidResult(
                f"the result names {output.item_id!r}, not the triggered {trigger.item_id!r}"
            )
        artifact = Artifact(
            version=ARTIFACT_VERSION,
            automation=trigger.automation,
            item_id=output.item_id,
            revision=snapshot.revision,
            payload=output.payload,
        ).validated()
        self._artifacts.save(artifact)
        return self._advance(record, RunState.ARTIFACT_PERSISTED), artifact

    # 9. Re-read the current work-item state and validate the result against it.
    def _validate(self, record: RunRecord, trigger: Trigger, artifact: Artifact) -> RunRecord:
        current = self._provider.read(trigger.item_id)
        if current is None or current.revision != artifact.revision:
            raise StaleWorkItem("the work item changed while the run was in flight")
        return self._advance(record, RunState.VALIDATED)

    # 10. Perform privileged publication through the trusted boundary.
    def _publish(
        self, record: RunRecord, trigger: Trigger, artifact: Artifact, lease: Lease
    ) -> RunRecord:
        if not self._leases.is_current(lease, self._clock.now()):
            raise LeaseLost("the lease expired or was taken over before publication")
        self._provider.publish(
            Publication(
                automation=trigger.automation,
                item_id=trigger.item_id,
                expected_revision=artifact.revision,
                artifact_id=artifact.artifact_id,
                summary=_summary(artifact.payload),
            )
        )
        return self._advance(record, RunState.PUBLISHED)

    # The record-keeping helpers.
    def _begin(self, trigger: Trigger) -> RunRecord:
        record = RunRecord(
            run_id=trigger.trigger_id,
            trigger_id=trigger.trigger_id,
            automation=trigger.automation,
            item_id=trigger.item_id,
            sequence=trigger.sequence,
            state=RunState.RECEIVED,
            finalization=None,
            detail="received",
            history=(RunState.RECEIVED,),
        )
        self._runs.put(record)
        return record

    def _advance(self, record: RunRecord, state: RunState) -> RunRecord:
        require_transition(record.state, state)
        advanced: RunRecord = replace(record, state=state, history=(*record.history, state))
        self._runs.put(advanced)
        return advanced

    def _finalize(self, record: RunRecord, finalization: Finalization, detail: str) -> RunRecord:
        require_transition(record.state, RunState.FINALIZED)
        finalized: RunRecord = replace(
            record,
            state=RunState.FINALIZED,
            finalization=finalization,
            detail=detail,
            history=(*record.history, RunState.FINALIZED),
        )
        self._runs.put(finalized)
        return finalized


def _summary(payload: Mapping[str, object]) -> str:
    summary = payload.get("summary")
    if isinstance(summary, str):
        return summary
    return ""
