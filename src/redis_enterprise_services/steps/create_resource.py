import logging
from http import HTTPStatus

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.exceptions.cluster import ClusterRequestError
from redis_enterprise_services.resources.completion import CompletionWaiter
from redis_enterprise_services.resources.models import CreatedResource
from redis_enterprise_services.resources.repository import ResourceRepository
from redis_enterprise_services.resources.spec import NamedSpec
from redis_enterprise_services.steps.result import KeepResult

logger: logging.Logger = logging.getLogger(name=__name__)


class CreateResourceStep[TSpec: NamedSpec]:
    def __init__(self, *, repository: ResourceRepository[TSpec], waiter: CompletionWaiter) -> None:
        self._repository: ResourceRepository[TSpec] = repository
        self._waiter: CompletionWaiter = waiter

    def execute(
        self, *, target: ClusterTarget, spec: TSpec, keep_result: KeepResult[CreatedResource]
    ) -> None:
        created: CreatedResource = self._repository.create(target=target, spec=spec)
        keep_result(created)
        self._waiter.wait_created(target=target, resource=created)

    def compensate(self, *, target: ClusterTarget, created: CreatedResource) -> None:
        logger.info(msg=f"removing created {created.name}")
        try:
            action_uid: str | None = self._repository.delete(target=target, uid=created.uid)
        except ClusterRequestError as error:
            if error.cluster_status_code != HTTPStatus.NOT_FOUND:
                raise
            logger.info(msg=f"{created.name} is already gone")
            return
        self._waiter.wait_deleted(target=target, uid=created.uid, action_uid=action_uid)
