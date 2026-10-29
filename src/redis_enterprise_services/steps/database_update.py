import logging

from pydantic import BaseModel, ConfigDict, JsonValue

from redis_enterprise_services.cluster.credentials import ClusterCredentialsProvider
from redis_enterprise_services.cluster.models import ClusterAddress, ClusterTarget
from redis_enterprise_services.databases.active_waiter import DatabaseActiveWaiter
from redis_enterprise_services.databases.models import DatabaseFields
from redis_enterprise_services.databases.repository import DatabaseRepository
from redis_enterprise_services.exceptions.cluster import UnrestorableFieldsError
from redis_enterprise_services.saga.contract.kind import StepKind
from redis_enterprise_services.saga.contract.result import KeepResult
from redis_enterprise_services.saga.contract.saga_step import SagaStep

logger: logging.Logger = logging.getLogger(name=__name__)


class DatabaseUpdateInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    cluster: ClusterAddress
    uid: int
    values: dict[str, JsonValue]


class DatabaseUpdate(SagaStep[DatabaseUpdateInput, DatabaseFields]):
    def __init__(
        self,
        *,
        repository: DatabaseRepository,
        active_waiter: DatabaseActiveWaiter,
        credentials: ClusterCredentialsProvider,
    ) -> None:
        self._repository: DatabaseRepository = repository
        self._active_waiter: DatabaseActiveWaiter = active_waiter
        self._credentials: ClusterCredentialsProvider = credentials

    @property
    def kind(self) -> StepKind:
        return StepKind.COMPENSATABLE

    def execute(self, *, step_input: DatabaseUpdateInput, keep_result: KeepResult[DatabaseFields]) -> None:
        snapshot: DatabaseFields = self._read(step_input=step_input, fields=list(step_input.values))
        ensure_restorable(step_input=step_input, snapshot=snapshot)
        keep_result(result=snapshot)
        self._apply(
            step_input=step_input, values=step_input.values, cluster_state_id=snapshot.cluster_state_id
        )

    def find_outcome(
        self, *, step_input: DatabaseUpdateInput, kept: DatabaseFields | None
    ) -> DatabaseFields | None:
        if kept is None:
            return None
        current: DatabaseFields = self._read(step_input=step_input, fields=list(step_input.values))
        if current.values != step_input.values:
            return None
        self._active_waiter.wait(target=self._target(step_input=step_input), uid=step_input.uid)
        return kept

    def compensate(self, *, step_input: DatabaseUpdateInput, result: DatabaseFields) -> None:
        logger.info(msg=f"restoring {sorted(result.values)} of database {step_input.uid}")
        current: DatabaseFields = self._read(step_input=step_input, fields=list(result.values))
        if current.values == result.values:
            logger.info(msg=f"database {step_input.uid} already has its old values")
            return
        self._apply(step_input=step_input, values=result.values, cluster_state_id=current.cluster_state_id)

    def _read(self, *, step_input: DatabaseUpdateInput, fields: list[str]) -> DatabaseFields:
        return self._repository.get_fields(
            target=self._target(step_input=step_input), uid=step_input.uid, fields=fields
        )

    def _apply(
        self, *, step_input: DatabaseUpdateInput, values: dict[str, JsonValue], cluster_state_id: int
    ) -> None:
        target: ClusterTarget = self._target(step_input=step_input)
        self._repository.update(
            target=target, uid=step_input.uid, values=values, cluster_state_id=cluster_state_id
        )
        self._active_waiter.wait(target=target, uid=step_input.uid)

    def _target(self, *, step_input: DatabaseUpdateInput) -> ClusterTarget:
        return self._credentials.target_for(address=step_input.cluster)


def ensure_restorable(*, step_input: DatabaseUpdateInput, snapshot: DatabaseFields) -> None:
    missing: set[str] = set(step_input.values) - set(snapshot.values)
    if missing:
        raise UnrestorableFieldsError(
            message=f"fields {sorted(missing)} are not set on database {step_input.uid}, cannot restore"
        )
