import logging
from http import HTTPStatus

from redis_enterprise_services.cluster.credentials import ClusterCredentialsProvider
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.exceptions.cluster import AmbiguousResourceError, ClusterRequestError
from redis_enterprise_services.resources.completion import CompletionWaiter
from redis_enterprise_services.resources.models import CreatedResource, CreateResourceInput, NamedResource
from redis_enterprise_services.resources.repository import ResourceRepository
from redis_enterprise_services.resources.spec import NamedSpec
from redis_enterprise_services.saga.contract.kind import StepKind
from redis_enterprise_services.saga.contract.result import KeepResult
from redis_enterprise_services.saga.contract.saga_step import SagaStep

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
        keep_result(result=created)
        self._waiter.wait_created(target=target, resource=created)

    def find_outcome(
        self, *, step_input: CreateResourceInput[TSpec], kept: CreatedResource | None
    ) -> CreatedResource | None:
        target: ClusterTarget = self._credentials.target_for(address=step_input.cluster)
        outcome: CreatedResource | None = (
            kept if kept is not None else self._find_by_name(target=target, step_input=step_input)
        )
        if outcome is not None:
            self._waiter.wait_created(target=target, resource=outcome)
        return outcome

    def _find_by_name(
        self, *, target: ClusterTarget, step_input: CreateResourceInput[TSpec]
    ) -> CreatedResource | None:
        found: list[NamedResource] = self._repository.find_by_name(target=target, name=step_input.spec.name)
        if not found:
            return None
        if len(found) > 1:
            raise AmbiguousResourceError(
                message=f"{len(found)} resources named {step_input.spec.name}: {[r.uid for r in found]}"
            )
        return CreatedResource(uid=found[0].uid, name=found[0].name, action_uid=None)

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
