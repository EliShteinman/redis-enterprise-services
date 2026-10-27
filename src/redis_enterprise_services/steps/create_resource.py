import logging
from http import HTTPStatus

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.exceptions.cluster import ClusterRequestError
from redis_enterprise_services.resources.completion import CompletionWaiter
from redis_enterprise_services.resources.models import CreatedResource
from redis_enterprise_services.resources.repository import ResourceRepository
from redis_enterprise_services.resources.spec import NamedSpec

logger: logging.Logger = logging.getLogger(name=__name__)


class CreateResourceStep[TSpec: NamedSpec]:
    def __init__(
        self,
        *,
        repository: ResourceRepository[TSpec],
        waiter: CompletionWaiter,
        target: ClusterTarget,
        spec: TSpec,
    ) -> None:
        self._repository: ResourceRepository[TSpec] = repository
        self._waiter: CompletionWaiter = waiter
        self._target: ClusterTarget = target
        self._spec: TSpec = spec
        self._created: CreatedResource | None = None

    @property
    def created(self) -> CreatedResource | None:
        return self._created

    def execute(self) -> None:
        self._created = self._repository.create(target=self._target, spec=self._spec)
        self._waiter.wait_created(target=self._target, resource=self._created)

    def compensate(self) -> None:
        if self._created is None:
            return
        logger.info(msg=f"removing created {self._created.name}")
        try:
            action_uid: str | None = self._repository.delete(target=self._target, uid=self._created.uid)
        except ClusterRequestError as error:
            if error.cluster_status_code != HTTPStatus.NOT_FOUND:
                raise
            logger.info(msg=f"{self._created.name} is already gone")
            return
        self._waiter.wait_deleted(target=self._target, uid=self._created.uid, action_uid=action_uid)
