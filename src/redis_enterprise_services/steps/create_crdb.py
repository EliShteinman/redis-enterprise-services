import logging
from collections.abc import Callable
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, JsonValue

from redis_enterprise_services.cluster.cluster_target_resolver import ClusterTargetResolver
from redis_enterprise_services.cluster.crdb_task_waiter import CrdbTaskWaiter
from redis_enterprise_services.cluster.json_body import required_string_field, string_field
from redis_enterprise_services.cluster.models import ClusterAddress, ClusterTarget
from redis_enterprise_services.cluster.rejection_kind import is_not_found
from redis_enterprise_services.config.crdb_settings import CrdbTaskSettings
from redis_enterprise_services.crdbs.repository import CrdbRepository
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.exceptions.cluster import ClusterRejectedRequestError, CrdbTaskTimeoutError
from redis_enterprise_services.saga.contract.keep_result import KeepResult
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.contract.step_kind import StepKind

logger: logging.Logger = logging.getLogger(name=__name__)


class CreateCrdbInput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    coordinator: ClusterAddress
    members: list[ClusterAddress]
    database: NewDatabase
    task_id: str


class CreatedCrdb(BaseModel):
    guid: str


class CreateCrdbStep(SagaStep[CreateCrdbInput, CreatedCrdb]):
    def __init__(
        self,
        *,
        repository: CrdbRepository,
        task_waiter: CrdbTaskWaiter,
        target_resolver: ClusterTargetResolver,
        task_settings: CrdbTaskSettings,
        status_field: str,
        new_task_id: Callable[[], str],
    ) -> None:
        self._repository: CrdbRepository = repository
        self._task_waiter: CrdbTaskWaiter = task_waiter
        self._target_resolver: ClusterTargetResolver = target_resolver
        self._task_settings: CrdbTaskSettings = task_settings
        self._status_field: str = status_field
        self._new_task_id: Callable[[], str] = new_task_id

    @property
    def kind(self) -> StepKind:
        return StepKind.COMPENSATABLE

    def execute(self, *, step_input: CreateCrdbInput, keep_result: KeepResult[CreatedCrdb]) -> None:
        coordinator: ClusterTarget = self._target(address=step_input.coordinator)
        self._repository.start_creation(
            coordinator=coordinator,
            members=[self._target(address=member) for member in step_input.members],
            database=step_input.database,
            task_id=step_input.task_id,
        )
        task: JsonValue = self._task_waiter.wait_until_finished(
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
        task: JsonValue | None = self._task_or_none(step_input=step_input)
        if task is None:
            return None
        status: str | None = string_field(body=task, name=self._status_field)
        if status in self._task_settings.failed_statuses:
            logger.info(msg=f"CRDB task {step_input.task_id} ended as {status}, which leaves nothing behind")
            return None
        if status != self._task_settings.completed_status:
            raise CrdbTaskTimeoutError(message=f"CRDB task {step_input.task_id} is still {status}")
        found: CreatedCrdb = CreatedCrdb(guid=self._guid_of(task=task, task_id=step_input.task_id))
        keep_result_if_none_kept(result=found)
        return found

    def compensate(self, *, step_input: CreateCrdbInput, result: CreatedCrdb) -> None:
        logger.info(msg=f"deleting CRDB {result.guid}")
        coordinator: ClusterTarget = self._target(address=step_input.coordinator)
        task_id: str = self._new_task_id()
        try:
            self._repository.start_deletion(target=coordinator, guid=result.guid, task_id=task_id)
        except ClusterRejectedRequestError as error:
            if not is_not_found(error=error):
                raise
            logger.info(msg=f"CRDB {result.guid} is already gone")
            return
        self._task_waiter.wait_until_finished(target=coordinator, task_id=task_id)

    def _exists(self, *, step_input: CreateCrdbInput, guid: str) -> bool:
        try:
            self._repository.read(target=self._target(address=step_input.coordinator), guid=guid)
        except ClusterRejectedRequestError as error:
            if not is_not_found(error=error):
                raise
            return False
        return True

    def _task_or_none(self, *, step_input: CreateCrdbInput) -> JsonValue | None:
        try:
            return self._task_waiter.read_task(
                target=self._target(address=step_input.coordinator), task_id=step_input.task_id
            )
        except ClusterRejectedRequestError as error:
            if not is_not_found(error=error):
                raise
            logger.info(msg=f"CRDB task {step_input.task_id} is unknown to the cluster, so it never started")
            return None

    def _guid_of(self, *, task: JsonValue, task_id: str) -> str:
        return required_string_field(
            body=task,
            name=self._task_settings.guid_field,
            missing_message=f"CRDB task {task_id} finished without {self._task_settings.guid_field}",
        )

    def _target(self, *, address: ClusterAddress) -> ClusterTarget:
        return self._target_resolver.target_for(address=address)
