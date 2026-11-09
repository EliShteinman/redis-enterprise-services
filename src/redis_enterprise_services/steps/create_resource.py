import logging

from redis_enterprise_services.cluster.cluster_target_resolver import ClusterTargetResolver
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster.rejection_kind import is_not_found
from redis_enterprise_services.exceptions.cluster import (
    ClusterRejectedRequestError,
    IncompleteClusterObjectError,
)
from redis_enterprise_services.resources.models import (
    CreatedResource,
    CreateResourceInput,
    DeletionStarted,
    NamedResource,
)
from redis_enterprise_services.resources.named_spec import NamedSpec
from redis_enterprise_services.resources.only_one_named import only_one_named
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
        missing: list[str] = self._repository.missing_fields(spec=step_input.spec, created=created)
        keep_result(result=self._repository.without_secrets(created=created))
        raise_if_incomplete(created=created, missing=missing)
        self._completion_waiter.wait_for_pending_creation(target=target, resource=created)

    def find_outcome(
        self,
        *,
        step_input: CreateResourceInput[TSpec],
        kept_result: CreatedResource | None,
        keep_result_if_none_kept: KeepResult[CreatedResource],
    ) -> CreatedResource | None:
        target: ClusterTarget = self._target_resolver.target_for(address=step_input.cluster)
        current: CreatedResource | None = self._read_current(
            target=target, step_input=step_input, kept_result=kept_result
        )
        if current is None:
            return None
        missing: list[str] = self._repository.missing_fields(spec=step_input.spec, created=current)
        kept: CreatedResource = kept_result or self._repository.without_secrets(created=current)
        keep_result_if_none_kept(result=kept)
        raise_if_incomplete(created=current, missing=missing)
        self._completion_waiter.wait_for_pending_creation(target=target, resource=kept)
        return kept

    def _read_current(
        self,
        *,
        target: ClusterTarget,
        step_input: CreateResourceInput[TSpec],
        kept_result: CreatedResource | None,
    ) -> CreatedResource | None:
        if kept_result is not None:
            return self._repository.read_created(target=target, uid=kept_result.uid)
        found: NamedResource | None = only_one_named(
            found=self._repository.find_by_name(target=target, name=step_input.spec.name),
            name=step_input.spec.name,
        )
        if found is None:
            return None
        return self._repository.read_created(target=target, uid=found.uid)

    def compensate(self, *, step_input: CreateResourceInput[TSpec], result: CreatedResource) -> None:
        logger.info(msg=f"removing created {result.name}")
        target: ClusterTarget = self._target_resolver.target_for(address=step_input.cluster)
        try:
            deletion: DeletionStarted = self._repository.start_deletion(target=target, uid=result.uid)
        except ClusterRejectedRequestError as error:
            if not is_not_found(error=error):
                raise
            logger.info(msg=f"{result.name} is already gone")
            return
        self._completion_waiter.wait_for_pending_deletion(
            target=target, uid=result.uid, action_uid=deletion.action_uid
        )


def raise_if_incomplete(*, created: CreatedResource, missing: list[str]) -> None:
    if missing:
        raise IncompleteClusterObjectError(
            message=f"created {created.name} (uid {created.uid}) came back without a value for {missing}"
        )
