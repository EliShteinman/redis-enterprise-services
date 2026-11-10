from pydantic import JsonValue

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster.read_again_polling import ReadAgainPolling
from redis_enterprise_services.cluster.rejection_kind import is_not_found
from redis_enterprise_services.cluster.status_goal import StatusGoal
from redis_enterprise_services.cluster.status_polling import StatusPolling
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.databases.database_activation_waiter import DatabaseActivationWaiter
from redis_enterprise_services.databases.database_fields_repository import DatabaseFieldsReader
from redis_enterprise_services.databases.models import DatabaseFieldsSnapshot
from redis_enterprise_services.exceptions.cluster import (
    ClusterRejectedRequestError,
    DatabaseActivationTimeoutError,
    DatabaseCreationFailedError,
    DatabaseDeletionTimeoutError,
)
from redis_enterprise_services.resources.models import CreatedResource
from redis_enterprise_services.resources.resource_completion_waiter import ResourceCompletionWaiter


class PollingDatabaseWaiter(DatabaseActivationWaiter, ResourceCompletionWaiter):
    def __init__(
        self,
        *,
        fields_reader: DatabaseFieldsReader,
        read_again_polling: ReadAgainPolling,
        status_polling: StatusPolling,
        settings: DatabaseSettings,
    ) -> None:
        self._fields_reader: DatabaseFieldsReader = fields_reader
        self._read_again_polling: ReadAgainPolling = read_again_polling
        self._status_polling: StatusPolling = status_polling
        self._settings: DatabaseSettings = settings

    def wait_until_active(self, *, target: ClusterTarget, uid: int) -> DatabaseFieldsSnapshot:
        return self._status_polling.wait_for(
            read=lambda: self._fields_reader.read(target=target, uid=uid),
            fields_of=snapshot_fields,
            goal=self._activation_goal(uid=uid),
            subject=database_subject(uid=uid),
            wait=self._settings.wait,
        )

    def wait_for_pending_creation(self, *, target: ClusterTarget, resource: CreatedResource) -> None:
        self.wait_until_active(target=target, uid=resource.uid)

    def wait_for_pending_deletion(self, *, target: ClusterTarget, uid: int, action_uid: str | None) -> None:
        if self._read_again_polling.poll_until(
            is_done=lambda: self._read_whether_deleted(target=target, uid=uid),
            wait=self._settings.wait,
            subject=database_subject(uid=uid),
        ):
            return
        raise DatabaseDeletionTimeoutError(
            message=f"database {uid} still exists after {self._settings.wait.timeout_seconds} seconds"
        )

    def _activation_goal(self, *, uid: int) -> StatusGoal[DatabaseFieldsSnapshot]:
        return StatusGoal[DatabaseFieldsSnapshot](
            done_status=self._settings.active_status,
            failed_statuses=frozenset({self._settings.creation_failed_status}),
            failed=lambda status, _snapshot: DatabaseCreationFailedError(
                message=f"database {uid} is {status}"
            ),
            timed_out=lambda: DatabaseActivationTimeoutError(
                message=f"database {uid} is not {self._settings.active_status} "
                f"after {self._settings.wait.timeout_seconds} seconds"
            ),
        )

    def _read_whether_deleted(self, *, target: ClusterTarget, uid: int) -> bool:
        try:
            self._fields_reader.read(target=target, uid=uid)
        except ClusterRejectedRequestError as error:
            if is_not_found(error=error):
                return True
            raise
        return False


def database_subject(*, uid: int) -> str:
    return f"database {uid}"


def snapshot_fields(snapshot: DatabaseFieldsSnapshot) -> JsonValue:
    return snapshot.values
