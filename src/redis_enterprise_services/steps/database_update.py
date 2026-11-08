import logging
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, JsonValue

from redis_enterprise_services.cluster.cluster_target_resolver import ClusterTargetResolver
from redis_enterprise_services.cluster.models import ClusterAddress, ClusterTarget
from redis_enterprise_services.databases.database_activation_waiter import DatabaseActivationWaiter
from redis_enterprise_services.databases.database_fields_repository import DatabaseFieldsRepository
from redis_enterprise_services.databases.models import DatabaseFields
from redis_enterprise_services.exceptions.cluster import UnrestorableFieldsError, UpdateOutcomeUnclearError
from redis_enterprise_services.saga.contract.keep_result import KeepResult
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.steps.same_values import same_values

logger: logging.Logger = logging.getLogger(name=__name__)


class DatabaseUpdateInput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    cluster: ClusterAddress
    uid: int
    values: dict[str, JsonValue]


class DatabaseUpdate(SagaStep[DatabaseUpdateInput, DatabaseFields]):
    def __init__(
        self,
        *,
        repository: DatabaseFieldsRepository,
        activation_waiter: DatabaseActivationWaiter,
        credentials: ClusterTargetResolver,
        unordered_fields: frozenset[str],
    ) -> None:
        self._repository: DatabaseFieldsRepository = repository
        self._unordered_fields: frozenset[str] = unordered_fields
        self._activation_waiter: DatabaseActivationWaiter = activation_waiter
        self._credentials: ClusterTargetResolver = credentials

    @property
    def kind(self) -> StepKind:
        return StepKind.COMPENSATABLE

    def execute(self, *, step_input: DatabaseUpdateInput, keep_result: KeepResult[DatabaseFields]) -> None:
        snapshot: DatabaseFields = self._read(step_input=step_input, field_names=list(step_input.values))
        ensure_restorable(step_input=step_input, snapshot=snapshot)
        keep_result(result=snapshot)
        self._apply(
            step_input=step_input, values=step_input.values, cluster_state_id=snapshot.cluster_state_id
        )

    def find_outcome(
        self,
        *,
        step_input: DatabaseUpdateInput,
        kept_result: DatabaseFields | None,
        keep_found_result: KeepResult[DatabaseFields],
    ) -> DatabaseFields | None:
        if kept_result is None:
            return None
        current: DatabaseFields = self._read(step_input=step_input, field_names=list(step_input.values))
        if not self._same(stored=current.values, wanted=step_input.values):
            return self._not_applied(step_input=step_input, current=current, kept_result=kept_result)
        self._activation_waiter.wait_until_active(
            target=self._target(step_input=step_input), uid=step_input.uid
        )
        return kept_result

    def compensate(self, *, step_input: DatabaseUpdateInput, result: DatabaseFields) -> None:
        logger.info(msg=f"restoring {sorted(result.values)} of database {step_input.uid}")
        current: DatabaseFields = self._read(step_input=step_input, field_names=list(result.values))
        if self._same(stored=current.values, wanted=result.values):
            logger.info(msg=f"database {step_input.uid} already has its old values")
            return
        if not self._same(stored=current.values, wanted=step_input.values):
            raise UpdateOutcomeUnclearError(
                message=f"database {step_input.uid} changed after the update, not restored over that change"
            )
        self._apply(step_input=step_input, values=result.values, cluster_state_id=current.cluster_state_id)

    def _not_applied(
        self, *, step_input: DatabaseUpdateInput, current: DatabaseFields, kept_result: DatabaseFields
    ) -> None:
        if self._same(stored=current.values, wanted=kept_result.values):
            return
        fields: list[str] = sorted(step_input.values)
        raise UpdateOutcomeUnclearError(
            message=f"database {step_input.uid} holds neither the old nor the new values of {fields}"
        )

    def _same(self, *, stored: dict[str, JsonValue], wanted: dict[str, JsonValue]) -> bool:
        return same_values(stored=stored, wanted=wanted, unordered_fields=self._unordered_fields)

    def _read(self, *, step_input: DatabaseUpdateInput, field_names: list[str]) -> DatabaseFields:
        return self._repository.get_fields(
            target=self._target(step_input=step_input), uid=step_input.uid, field_names=field_names
        )

    def _apply(
        self, *, step_input: DatabaseUpdateInput, values: dict[str, JsonValue], cluster_state_id: int
    ) -> None:
        target: ClusterTarget = self._target(step_input=step_input)
        self._repository.update_fields(
            target=target, uid=step_input.uid, values=values, cluster_state_id=cluster_state_id
        )
        self._activation_waiter.wait_until_active(target=target, uid=step_input.uid)

    def _target(self, *, step_input: DatabaseUpdateInput) -> ClusterTarget:
        return self._credentials.target_for(address=step_input.cluster)


def ensure_restorable(*, step_input: DatabaseUpdateInput, snapshot: DatabaseFields) -> None:
    missing: set[str] = set(step_input.values) - set(snapshot.values)
    if missing:
        raise UnrestorableFieldsError(
            message=f"fields {sorted(missing)} are not set on database {step_input.uid}, cannot restore"
        )
