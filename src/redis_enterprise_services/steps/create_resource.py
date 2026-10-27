import logging
from http import HTTPStatus

from redis_enterprise_services.cluster.credentials import ClusterCredentialsProvider
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.exceptions.cluster import ClusterRequestError
from redis_enterprise_services.resources.completion import CompletionWaiter
from redis_enterprise_services.resources.models import CreatedResource, CreateResourceInput, NamedResource
from redis_enterprise_services.resources.repository import ResourceRepository
from redis_enterprise_services.resources.spec import NamedSpec
from redis_enterprise_services.steps.kind import StepKind
from redis_enterprise_services.steps.result import KeepResult
from redis_enterprise_services.steps.saga_step import SagaStep

logger: logging.Logger = logging.getLogger(name=__name__)


class CreateResourceStep[TSpec: NamedSpec](SagaStep[CreateResourceInput[TSpec], CreatedResource]):
    def __init__(
        self,
        *,
        repository: ResourceRepository[TSpec],
        waiter: CompletionWaiter,
        credentials: ClusterCredentialsProvider,
    ) -> None:
        self._repository: ResourceRepository[TSpec] = repository
        self._waiter: CompletionWaiter = waiter
        self._credentials: ClusterCredentialsProvider = credentials

    @property
    def kind(self) -> StepKind:
        return StepKind.COMPENSATABLE

    def execute(
        self, *, step_input: CreateResourceInput[TSpec], keep_result: KeepResult[CreatedResource]
    ) -> None:
        target: ClusterTarget = self._credentials.target_for(address=step_input.cluster)
        created: CreatedResource = self._repository.create(target=target, spec=step_input.spec)
        keep_result(created)
        self._waiter.wait_created(target=target, resource=created)

    def find_outcome(
        self, *, step_input: CreateResourceInput[TSpec], kept: CreatedResource | None
    ) -> CreatedResource | None:
        found: NamedResource | None = self._repository.find_by_name(
            target=self._credentials.target_for(address=step_input.cluster), name=step_input.spec.name
        )
        if found is None:
            return None
        return CreatedResource(uid=found.uid, name=found.name, action_uid=None)

    def compensate(self, *, step_input: CreateResourceInput[TSpec], result: CreatedResource) -> None:
        logger.info(msg=f"removing created {result.name}")
        target: ClusterTarget = self._credentials.target_for(address=step_input.cluster)
        try:
            action_uid: str | None = self._repository.delete(target=target, uid=result.uid)
        except ClusterRequestError as error:
            if error.cluster_status_code != HTTPStatus.NOT_FOUND:
                raise
            logger.info(msg=f"{result.name} is already gone")
            return
        self._waiter.wait_deleted(target=target, uid=result.uid, action_uid=action_uid)
