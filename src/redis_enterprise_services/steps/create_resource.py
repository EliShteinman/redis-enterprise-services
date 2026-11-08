import logging
from http import HTTPStatus

from redis_enterprise_services.cluster.cluster_target_resolver import ClusterTargetResolver
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.exceptions.cluster import (
    ClusterRejectedRequestError,
    DuplicateResourceNameError,
)
from redis_enterprise_services.resources.models import CreatedResource, CreateResourceInput, NamedResource
from redis_enterprise_services.resources.named_spec import NamedSpec
from redis_enterprise_services.resources.repository import ResourceRepository
from redis_enterprise_services.resources.resource_completion_waiter import ResourceCompletionWaiter
from redis_enterprise_services.saga.contract.keep_result import KeepResult
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.contract.step_kind import StepKind

logger: logging.Logger = logging.getLogger(name=__name__)


class CreateResourceStep[TSpec: NamedSpec](SagaStep[CreateResourceInput[TSpec], CreatedResource]):
    def __init__(
        self,
        *,
        repository: ResourceRepository[TSpec],
        completion_waiter: ResourceCompletionWaiter,
        target_resolver: ClusterTargetResolver,
    ) -> None:
        self._repository: ResourceRepository[TSpec] = repository
        self._completion_waiter: ResourceCompletionWaiter = completion_waiter
        self._target_resolver: ClusterTargetResolver = target_resolver

    @property
    def kind(self) -> StepKind:
        return StepKind.COMPENSATABLE

    def execute(
        self, *, step_input: CreateResourceInput[TSpec], keep_result: KeepResult[CreatedResource]
    ) -> None:
        target: ClusterTarget = self._target_resolver.target_for(address=step_input.cluster)
        created: CreatedResource = self._repository.start_creation(target=target, spec=step_input.spec)
        keep_result(result=created)
        self._completion_waiter.wait_for_pending_creation(target=target, resource=created)

    def find_outcome(
        self,
        *,
        step_input: CreateResourceInput[TSpec],
        kept_result: CreatedResource | None,
        keep_found_result: KeepResult[CreatedResource],
    ) -> CreatedResource | None:
        target: ClusterTarget = self._target_resolver.target_for(address=step_input.cluster)
        created: CreatedResource | None = (
            kept_result
            if kept_result is not None
            else self._find_only_one_by_name(target=target, step_input=step_input)
        )
        if created is not None:
            keep_found_result(result=created)
            self._completion_waiter.wait_for_pending_creation(target=target, resource=created)
        return created

    def _find_only_one_by_name(
        self, *, target: ClusterTarget, step_input: CreateResourceInput[TSpec]
    ) -> CreatedResource | None:
        found: list[NamedResource] = self._repository.find_by_name(target=target, name=step_input.spec.name)
        if not found:
            return None
        if len(found) > 1:
            uids: list[int] = [resource.uid for resource in found]
            raise DuplicateResourceNameError(
                message=f"{len(found)} resources named {step_input.spec.name}: {uids}"
            )
        return CreatedResource(uid=found[0].uid, name=found[0].name, action_uid=None)

    def compensate(self, *, step_input: CreateResourceInput[TSpec], result: CreatedResource) -> None:
        logger.info(msg=f"removing created {result.name}")
        target: ClusterTarget = self._target_resolver.target_for(address=step_input.cluster)
        try:
            action_uid: str | None = self._repository.start_deletion(target=target, uid=result.uid)
        except ClusterRejectedRequestError as error:
            if error.cluster_status_code != HTTPStatus.NOT_FOUND:
                raise
            logger.info(msg=f"{result.name} is already gone")
            return
        self._completion_waiter.wait_for_pending_deletion(
            target=target, uid=result.uid, action_uid=action_uid
        )
