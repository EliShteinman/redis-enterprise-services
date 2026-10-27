import logging

from pydantic import JsonValue

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.databases.active_waiter import DatabaseActiveWaiter
from redis_enterprise_services.databases.models import DatabaseFields
from redis_enterprise_services.databases.repository import DatabaseRepository
from redis_enterprise_services.exceptions.cluster import UnrestorableFieldsError
from redis_enterprise_services.steps.result import KeepResult

logger: logging.Logger = logging.getLogger(name=__name__)


class DatabaseUpdate:
    def __init__(self, *, repository: DatabaseRepository, active_waiter: DatabaseActiveWaiter) -> None:
        self._repository: DatabaseRepository = repository
        self._active_waiter: DatabaseActiveWaiter = active_waiter

    def execute(
        self,
        *,
        target: ClusterTarget,
        uid: int,
        values: dict[str, JsonValue],
        keep_result: KeepResult[DatabaseFields],
    ) -> None:
        snapshot: DatabaseFields = self._repository.get_fields(target=target, uid=uid, fields=list(values))
        ensure_restorable(uid=uid, values=values, snapshot=snapshot)
        keep_result(snapshot)
        self._apply(target=target, uid=uid, values=values, cluster_state_id=snapshot.cluster_state_id)

    def compensate(self, *, target: ClusterTarget, uid: int, snapshot: DatabaseFields) -> None:
        logger.info(msg=f"restoring {sorted(snapshot.values)} of database {uid}")
        current: DatabaseFields = self._repository.get_fields(
            target=target, uid=uid, fields=list(snapshot.values)
        )
        self._apply(target=target, uid=uid, values=snapshot.values, cluster_state_id=current.cluster_state_id)

    def _apply(
        self, *, target: ClusterTarget, uid: int, values: dict[str, JsonValue], cluster_state_id: int
    ) -> None:
        self._repository.update(target=target, uid=uid, values=values, cluster_state_id=cluster_state_id)
        self._active_waiter.wait(target=target, uid=uid)


def ensure_restorable(*, uid: int, values: dict[str, JsonValue], snapshot: DatabaseFields) -> None:
    missing: set[str] = set(values) - set(snapshot.values)
    if missing:
        raise UnrestorableFieldsError(
            message=f"fields {sorted(missing)} are not set on database {uid} and cannot be restored"
        )
