import logging
import re
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from redis_enterprise_services.cluster.cluster_target_resolver import ClusterTargetResolver
from redis_enterprise_services.cluster.models import ClusterAddress, ClusterTarget
from redis_enterprise_services.crdbs.models import Crdb, CrdbInstance
from redis_enterprise_services.crdbs.repository import CrdbRepository
from redis_enterprise_services.databases.database_activation_waiter import DatabaseActivationWaiter
from redis_enterprise_services.exceptions.cluster import IncompleteClusterObjectError
from redis_enterprise_services.saga.contract.keep_result import KeepResult
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.contract.step_kind import StepKind

logger: logging.Logger = logging.getLogger(name=__name__)


class FindLocalCrdbInstanceInput(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    cluster: ClusterAddress
    guid: str


class LocalCrdbInstance(BaseModel):
    instance_id: int
    db_uid: int


class FindLocalCrdbInstanceStep(SagaStep[FindLocalCrdbInstanceInput, LocalCrdbInstance]):
    def __init__(
        self,
        *,
        repository: CrdbRepository,
        activation_waiter: DatabaseActivationWaiter,
        target_resolver: ClusterTargetResolver,
    ) -> None:
        self._repository: CrdbRepository = repository
        self._activation_waiter: DatabaseActivationWaiter = activation_waiter
        self._target_resolver: ClusterTargetResolver = target_resolver

    @property
    def kind(self) -> StepKind:
        return StepKind.COMPENSATABLE

    def execute(
        self, *, step_input: FindLocalCrdbInstanceInput, keep_result: KeepResult[LocalCrdbInstance]
    ) -> None:
        keep_result(result=self._active_local_instance(step_input=step_input))

    def find_outcome(
        self,
        *,
        step_input: FindLocalCrdbInstanceInput,
        kept_result: LocalCrdbInstance | None,
        keep_result_if_none_kept: KeepResult[LocalCrdbInstance],
    ) -> LocalCrdbInstance | None:
        if kept_result is not None:
            return kept_result
        found: LocalCrdbInstance = self._active_local_instance(step_input=step_input)
        keep_result_if_none_kept(result=found)
        return found

    def compensate(self, *, step_input: FindLocalCrdbInstanceInput, result: LocalCrdbInstance) -> None:
        logger.info(msg=f"nothing to undo for finding database {result.db_uid} of CRDB {step_input.guid}")

    def _active_local_instance(self, *, step_input: FindLocalCrdbInstanceInput) -> LocalCrdbInstance:
        target: ClusterTarget = self._target_resolver.target_for(address=step_input.cluster)
        crdb: Crdb = self._repository.read(target=target, guid=step_input.guid)
        local: LocalCrdbInstance = local_instance(crdb=crdb, api_url=target.api_url)
        self._activation_waiter.wait_until_active(target=target, uid=local.db_uid)
        return local


DB_UID: re.Pattern[str] = re.compile(pattern=r"[0-9]+")


def local_instance(*, crdb: Crdb, api_url: str) -> LocalCrdbInstance:
    instance: CrdbInstance | None = crdb.instance_on(api_url=api_url)
    if instance is None or instance.db_uid is None or not DB_UID.fullmatch(instance.db_uid):
        raise IncompleteClusterObjectError(
            message=f"CRDB {crdb.guid} read on {api_url} has no local database there"
        )
    return LocalCrdbInstance(instance_id=instance.id, db_uid=int(instance.db_uid))
