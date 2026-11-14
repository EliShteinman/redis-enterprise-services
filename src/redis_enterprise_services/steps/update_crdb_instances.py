import logging
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, JsonValue

from redis_enterprise_services.cluster.cluster_target_resolver import ClusterTargetResolver
from redis_enterprise_services.cluster.models import ClusterAddress, ClusterTarget
from redis_enterprise_services.crdbs.models import Crdb, CrdbInstance
from redis_enterprise_services.crdbs.repository import CrdbRepository
from redis_enterprise_services.exceptions.cluster import (
    CrdbTaskTimeoutError,
    IncompleteClusterObjectError,
    UnrestorableFieldsError,
    UpdateOutcomeUnclearError,
)
from redis_enterprise_services.saga.contract.keep_result import KeepResult
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.steps.crdb_task_tracker import CrdbTaskTracker
from redis_enterprise_services.steps.held_values import HeldValues, held_values
from redis_enterprise_services.steps.undo_task_id import undo_task_id

logger: logging.Logger = logging.getLogger(name=__name__)

type InstanceValues = dict[int, dict[str, JsonValue]]


class UpdateCrdbInstancesInput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    coordinator: ClusterAddress
    guid: str
    values_by_instance: InstanceValues
    task_id: str


class CrdbInstancesSnapshot(BaseModel):
    values_by_instance: InstanceValues


class UpdateCrdbInstancesStep(SagaStep[UpdateCrdbInstancesInput, CrdbInstancesSnapshot]):
    def __init__(
        self,
        *,
        repository: CrdbRepository,
        task_tracker: CrdbTaskTracker,
        target_resolver: ClusterTargetResolver,
        list_fields: frozenset[str],
    ) -> None:
        self._repository: CrdbRepository = repository
        self._task_tracker: CrdbTaskTracker = task_tracker
        self._target_resolver: ClusterTargetResolver = target_resolver
        self._list_fields: frozenset[str] = list_fields

    @property
    def kind(self) -> StepKind:
        return StepKind.COMPENSATABLE

    def execute(
        self, *, step_input: UpdateCrdbInstancesInput, keep_result: KeepResult[CrdbInstancesSnapshot]
    ) -> None:
        keep_result(result=self._current(step_input=step_input))
        self._apply(
            step_input=step_input,
            values_by_instance=step_input.values_by_instance,
            task_id=step_input.task_id,
        )

    def find_outcome(
        self,
        *,
        step_input: UpdateCrdbInstancesInput,
        kept_result: CrdbInstancesSnapshot | None,
        keep_result_if_none_kept: KeepResult[CrdbInstancesSnapshot],
    ) -> CrdbInstancesSnapshot | None:
        if kept_result is None:
            return None
        self._reject_a_running_task(step_input=step_input)
        match self._held(step_input=step_input, old=kept_result):
            case HeldValues.NEW | HeldValues.BOTH:
                return kept_result
            case HeldValues.OLD:
                return None
            case HeldValues.NEITHER:
                raise UpdateOutcomeUnclearError(
                    message=f"CRDB {step_input.guid} holds neither the old nor the new instance values"
                )

    def compensate(self, *, step_input: UpdateCrdbInstancesInput, result: CrdbInstancesSnapshot) -> None:
        logger.info(msg=f"restoring the instance values of CRDB {step_input.guid}")
        undo_id: str = undo_task_id(task_id=step_input.task_id)
        for task_id in (step_input.task_id, undo_id):
            self._task_tracker.settle(target=self._coordinator(step_input=step_input), task_id=task_id)
        match self._held(step_input=step_input, old=result):
            case HeldValues.OLD | HeldValues.BOTH:
                logger.info(msg=f"CRDB {step_input.guid} already has its old instance values")
            case HeldValues.NEW:
                self._apply(
                    step_input=step_input,
                    values_by_instance=result.values_by_instance,
                    task_id=undo_id,
                )
            case HeldValues.NEITHER:
                raise UpdateOutcomeUnclearError(
                    message=f"CRDB {step_input.guid} changed after the update, not restored over that change"
                )

    def _reject_a_running_task(self, *, step_input: UpdateCrdbInstancesInput) -> None:
        task: JsonValue | None = self._task_tracker.task_or_none(
            target=self._coordinator(step_input=step_input), task_id=step_input.task_id
        )
        if task is not None and self._task_tracker.is_running(task=task):
            raise CrdbTaskTimeoutError(
                message=f"CRDB task {step_input.task_id} is still {self._task_tracker.status_of(task=task)}"
            )

    def _held(self, *, step_input: UpdateCrdbInstancesInput, old: CrdbInstancesSnapshot) -> HeldValues:
        current: CrdbInstancesSnapshot = self._current(step_input=step_input)
        return held_values(
            current=flattened(values_by_instance=current.values_by_instance),
            new_values=flattened(values_by_instance=step_input.values_by_instance),
            old_values=flattened(values_by_instance=old.values_by_instance),
            order_insensitive_fields=frozenset(
                instance_field(instance_id=instance_id, name=name)
                for instance_id, values in step_input.values_by_instance.items()
                for name in values
                if name in self._list_fields
            ),
        )

    def _current(self, *, step_input: UpdateCrdbInstancesInput) -> CrdbInstancesSnapshot:
        crdb: Crdb = self._repository.read(
            target=self._coordinator(step_input=step_input), guid=step_input.guid
        )
        return CrdbInstancesSnapshot(
            values_by_instance={
                instance_id: self._instance_values(crdb=crdb, instance_id=instance_id, names=list(values))
                for instance_id, values in step_input.values_by_instance.items()
            }
        )

    def _instance_values(self, *, crdb: Crdb, instance_id: int, names: list[str]) -> dict[str, JsonValue]:
        instance: CrdbInstance | None = next((i for i in crdb.instances if i.id == instance_id), None)
        if instance is None:
            raise IncompleteClusterObjectError(message=f"CRDB {crdb.guid} has no instance {instance_id}")
        unrestorable: list[str] = [
            name for name in names if name not in instance.db_config and name not in self._list_fields
        ]
        if unrestorable:
            raise UnrestorableFieldsError(
                message=f"CRDB {crdb.guid} instance {instance_id} has no {unrestorable}, so an undo could "
                "not put them back"
            )
        return {name: instance.db_config.get(name, []) for name in names}

    def _apply(
        self, *, step_input: UpdateCrdbInstancesInput, values_by_instance: InstanceValues, task_id: str
    ) -> None:
        coordinator: ClusterTarget = self._coordinator(step_input=step_input)
        self._task_tracker.send_or_join(
            send=lambda: self._repository.start_instances_update(
                target=coordinator,
                guid=step_input.guid,
                values_by_instance=values_by_instance,
                task_id=task_id,
            ),
            task_id=task_id,
        )
        self._task_tracker.wait_until_finished(target=coordinator, task_id=task_id)

    def _coordinator(self, *, step_input: UpdateCrdbInstancesInput) -> ClusterTarget:
        return self._target_resolver.target_for(address=step_input.coordinator)


def instance_field(*, instance_id: int, name: str) -> str:
    return f"{instance_id}.{name}"


def flattened(*, values_by_instance: InstanceValues) -> dict[str, JsonValue]:
    return {
        instance_field(instance_id=instance_id, name=name): value
        for instance_id, values in values_by_instance.items()
        for name, value in values.items()
    }
