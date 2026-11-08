import logging
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, JsonValue

from redis_enterprise_services.cluster.cluster_target_resolver import ClusterTargetResolver
from redis_enterprise_services.cluster.models import ClusterAddress, ClusterTarget
from redis_enterprise_services.databases.database_activation_waiter import DatabaseActivationWaiter
from redis_enterprise_services.databases.database_fields_repository import DatabaseFieldsRepository
from redis_enterprise_services.databases.models import DatabaseFieldsSnapshot
from redis_enterprise_services.exceptions.cluster import UnrestorableFieldsError, UpdateOutcomeUnclearError
from redis_enterprise_services.saga.contract.keep_result import KeepResult
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.steps.same_values import same_values

logger: logging.Logger = logging.getLogger(name=__name__)


class UpdateDatabaseInput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    cluster: ClusterAddress
    uid: int
    values: dict[str, JsonValue]


class UpdateDatabaseStep(SagaStep[UpdateDatabaseInput, DatabaseFieldsSnapshot]):
    def __init__(
        self,
        *,
        repository: DatabaseFieldsRepository,
        activation_waiter: DatabaseActivationWaiter,
        target_resolver: ClusterTargetResolver,
        order_insensitive_fields: frozenset[str],
    ) -> None:
        self._repository: DatabaseFieldsRepository = repository
        self._order_insensitive_fields: frozenset[str] = order_insensitive_fields
        self._activation_waiter: DatabaseActivationWaiter = activation_waiter
        self._target_resolver: ClusterTargetResolver = target_resolver

    @property
    def kind(self) -> StepKind:
        return StepKind.COMPENSATABLE

    def execute(
        self, *, step_input: UpdateDatabaseInput, keep_result: KeepResult[DatabaseFieldsSnapshot]
    ) -> None:
        snapshot: DatabaseFieldsSnapshot = self._read_fields(
            step_input=step_input, field_names=list(step_input.values)
        )
        reject_fields_missing_from_snapshot(step_input=step_input, snapshot=snapshot)
        keep_result(result=snapshot)
        self._update_if_state_unchanged_and_wait_until_active(
            step_input=step_input, values=step_input.values, cluster_state_id=snapshot.cluster_state_id
        )

    def find_outcome(
        self,
        *,
        step_input: UpdateDatabaseInput,
        kept_result: DatabaseFieldsSnapshot | None,
        keep_found_result: KeepResult[DatabaseFieldsSnapshot],
    ) -> DatabaseFieldsSnapshot | None:
        if kept_result is None:
            return None
        current: DatabaseFieldsSnapshot = self._read_fields(
            step_input=step_input, field_names=list(step_input.values)
        )
        if not self._same(current=current.values, expected=step_input.values):
            self._raise_unless_old_values_remain(
                step_input=step_input, current=current, kept_result=kept_result
            )
            return None
        self._activation_waiter.wait_until_active(
            target=self._target(step_input=step_input), uid=step_input.uid
        )
        return kept_result

    def compensate(self, *, step_input: UpdateDatabaseInput, result: DatabaseFieldsSnapshot) -> None:
        logger.info(msg=f"restoring {sorted(result.values)} of database {step_input.uid}")
        current: DatabaseFieldsSnapshot = self._read_fields(
            step_input=step_input, field_names=list(result.values)
        )
        if self._same(current=current.values, expected=result.values):
            logger.info(msg=f"database {step_input.uid} already has its old values")
            return
        if not self._same(current=current.values, expected=step_input.values):
            raise UpdateOutcomeUnclearError(
                message=f"database {step_input.uid} changed after the update, not restored over that change"
            )
        self._update_if_state_unchanged_and_wait_until_active(
            step_input=step_input, values=result.values, cluster_state_id=current.cluster_state_id
        )

    def _raise_unless_old_values_remain(
        self,
        *,
        step_input: UpdateDatabaseInput,
        current: DatabaseFieldsSnapshot,
        kept_result: DatabaseFieldsSnapshot,
    ) -> None:
        if self._same(current=current.values, expected=kept_result.values):
            return
        fields: list[str] = sorted(step_input.values)
        raise UpdateOutcomeUnclearError(
            message=f"database {step_input.uid} holds neither the old nor the new values of {fields}"
        )

    def _same(self, *, current: dict[str, JsonValue], expected: dict[str, JsonValue]) -> bool:
        return same_values(
            current=current, expected=expected, order_insensitive_fields=self._order_insensitive_fields
        )

    def _read_fields(
        self, *, step_input: UpdateDatabaseInput, field_names: list[str]
    ) -> DatabaseFieldsSnapshot:
        return self._repository.read_fields(
            target=self._target(step_input=step_input), uid=step_input.uid, field_names=field_names
        )

    def _update_if_state_unchanged_and_wait_until_active(
        self, *, step_input: UpdateDatabaseInput, values: dict[str, JsonValue], cluster_state_id: int
    ) -> None:
        target: ClusterTarget = self._target(step_input=step_input)
        self._repository.update_fields_if_state_unchanged(
            target=target, uid=step_input.uid, values=values, cluster_state_id=cluster_state_id
        )
        self._activation_waiter.wait_until_active(target=target, uid=step_input.uid)

    def _target(self, *, step_input: UpdateDatabaseInput) -> ClusterTarget:
        return self._target_resolver.target_for(address=step_input.cluster)


def reject_fields_missing_from_snapshot(
    *, step_input: UpdateDatabaseInput, snapshot: DatabaseFieldsSnapshot
) -> None:
    missing: set[str] = set(step_input.values) - set(snapshot.values)
    if missing:
        raise UnrestorableFieldsError(
            message=f"fields {sorted(missing)} are not set on database {step_input.uid}, cannot restore"
        )
