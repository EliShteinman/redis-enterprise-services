import logging

from pydantic import JsonValue

from redis_enterprise_services.databases.models import DatabaseFields
from redis_enterprise_services.databases.repository import DatabaseRepository
from redis_enterprise_services.edge.models import ClusterTarget

logger: logging.Logger = logging.getLogger(name=__name__)


class DatabaseUpdate:
    def __init__(
        self,
        *,
        repository: DatabaseRepository,
        target: ClusterTarget,
        uid: int,
        values: dict[str, JsonValue],
    ) -> None:
        self._repository: DatabaseRepository = repository
        self._target: ClusterTarget = target
        self._uid: int = uid
        self._values: dict[str, JsonValue] = values
        self._snapshot: DatabaseFields | None = None

    def execute(self) -> None:
        self._snapshot = self._repository.get_fields(
            target=self._target, uid=self._uid, fields=list(self._values)
        )
        self._apply(values=self._values, cluster_state_id=self._snapshot.cluster_state_id)

    def compensate(self) -> None:
        if self._snapshot is None:
            return
        logger.info(msg=f"restoring {sorted(self._snapshot.values)} of database {self._uid}")
        current: DatabaseFields = self._repository.get_fields(
            target=self._target, uid=self._uid, fields=list(self._snapshot.values)
        )
        self._apply(values=self._snapshot.values, cluster_state_id=current.cluster_state_id)

    def _apply(self, *, values: dict[str, JsonValue], cluster_state_id: int | None) -> None:
        self._repository.update(
            target=self._target, uid=self._uid, values=values, cluster_state_id=cluster_state_id
        )
        self._repository.wait_until_active(target=self._target, uid=self._uid)
