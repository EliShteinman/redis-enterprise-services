import logging
from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, JsonValue, model_validator

from redis_enterprise_services.cluster.cluster_target_resolver import ClusterTargetResolver
from redis_enterprise_services.cluster.json_body import required_string_field
from redis_enterprise_services.cluster.models import ClusterAddress, ClusterTarget
from redis_enterprise_services.cluster.rejection_kind import is_not_found
from redis_enterprise_services.crdbs.repository import CrdbRepository
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.exceptions.cluster import ClusterRejectedRequestError
from redis_enterprise_services.exceptions.saga import StepNeedsManualInterventionError
from redis_enterprise_services.saga.contract.keep_result import KeepResult
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.steps.crdb_task_tracker import CrdbTaskTracker
from redis_enterprise_services.steps.undo_task_id import undo_task_id

logger: logging.Logger = logging.getLogger(name=__name__)


class CreateCrdbInput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    coordinator: ClusterAddress
    members: list[ClusterAddress]
    database: NewDatabase
    task_id: str

    @model_validator(mode="after")
    def reject_a_coordinator_outside_the_members(self) -> Self:
        if self.coordinator not in self.members:
            raise ValueError(f"the coordinator {self.coordinator.api_url} is not one of the CRDB members")
        return self


class CreatedCrdb(BaseModel):
    guid: str


class CreateCrdbStep(SagaStep[CreateCrdbInput, CreatedCrdb]):
    def __init__(
        self,
        *,
        repository: CrdbRepository,
        task_tracker: CrdbTaskTracker,
        target_resolver: ClusterTargetResolver,
        guid_field: str,
    ) -> None:
        self._repository: CrdbRepository = repository
        self._task_tracker: CrdbTaskTracker = task_tracker
        self._target_resolver: ClusterTargetResolver = target_resolver
        self._guid_field: str = guid_field

    @property
    def kind(self) -> StepKind:
        return StepKind.COMPENSATABLE

    def execute(self, *, step_input: CreateCrdbInput, keep_result: KeepResult[CreatedCrdb]) -> None:
        coordinator: ClusterTarget = self._target(address=step_input.coordinator)
        members: list[ClusterTarget] = [self._target(address=member) for member in step_input.members]
        self._task_tracker.send_or_join(
            send=lambda: self._repository.start_creation(
                coordinator=coordinator,
                members=members,
                database=step_input.database,
                task_id=step_input.task_id,
            ),
            task_id=step_input.task_id,
        )
        task: JsonValue = self._task_tracker.wait_until_finished(
            target=coordinator, task_id=step_input.task_id
        )
        keep_result(result=CreatedCrdb(guid=self._guid_of(task=task, task_id=step_input.task_id)))

    def find_outcome(
        self,
        *,
        step_input: CreateCrdbInput,
        kept_result: CreatedCrdb | None,
        keep_result_if_none_kept: KeepResult[CreatedCrdb],
    ) -> CreatedCrdb | None:
        if kept_result is not None:
            return kept_result if self._exists(step_input=step_input, guid=kept_result.guid) else None
        coordinator: ClusterTarget = self._target(address=step_input.coordinator)
        task: JsonValue | None = self._task_tracker.task_or_none(
            target=coordinator, task_id=step_input.task_id
        )
        if task is None:
            self._reject_a_crdb_left_without_its_task(step_input=step_input)
            logger.info(msg=f"CRDB task {step_input.task_id} never ran, which leaves nothing behind")
            return None
        self._task_tracker.reject_an_unfinished_task(
            target=coordinator, task=task, task_id=step_input.task_id
        )
        found: CreatedCrdb = CreatedCrdb(guid=self._guid_of(task=task, task_id=step_input.task_id))
        keep_result_if_none_kept(result=found)
        return found

    def compensate(self, *, step_input: CreateCrdbInput, result: CreatedCrdb) -> None:
        logger.info(msg=f"deleting CRDB {result.guid}")
        coordinator: ClusterTarget = self._target(address=step_input.coordinator)
        task_id: str = undo_task_id(task_id=step_input.task_id)
        try:
            self._task_tracker.send_or_join(
                send=lambda: self._repository.start_deletion(
                    target=coordinator, guid=result.guid, task_id=task_id
                ),
                task_id=task_id,
            )
        except ClusterRejectedRequestError as error:
            if not is_not_found(error=error):
                raise
            logger.info(msg=f"CRDB {result.guid} is already gone")
            return
        self._task_tracker.wait_until_finished(target=coordinator, task_id=task_id)

    def _reject_a_crdb_left_without_its_task(self, *, step_input: CreateCrdbInput) -> None:
        coordinator: ClusterTarget = self._target(address=step_input.coordinator)
        if step_input.database.name in self._repository.list_crdb_names(target=coordinator):
            raise StepNeedsManualInterventionError(
                message=f"CRDB task {step_input.task_id} is unknown, perhaps expired, but a CRDB named "
                f"{step_input.database.name} exists, so it may be this creation's"
            )

    def _exists(self, *, step_input: CreateCrdbInput, guid: str) -> bool:
        try:
            self._repository.read(target=self._target(address=step_input.coordinator), guid=guid)
        except ClusterRejectedRequestError as error:
            if not is_not_found(error=error):
                raise
            return False
        return True

    def _guid_of(self, *, task: JsonValue, task_id: str) -> str:
        return required_string_field(
            body=task,
            name=self._guid_field,
            missing_message=f"CRDB task {task_id} finished without {self._guid_field}",
        )

    def _target(self, *, address: ClusterAddress) -> ClusterTarget:
        return self._target_resolver.target_for(address=address)
