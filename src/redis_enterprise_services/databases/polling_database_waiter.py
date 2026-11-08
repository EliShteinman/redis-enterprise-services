import logging
from collections.abc import Callable

from pydantic import JsonValue

from redis_enterprise_services.cluster.json_body import required_string_field
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster.read_again_polling import ReadAgainPolling
from redis_enterprise_services.cluster.rejection_kind import is_not_found
from redis_enterprise_services.config.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.databases.database_activation_waiter import DatabaseActivationWaiter
from redis_enterprise_services.databases.database_fields_repository import DatabaseFieldsReader
from redis_enterprise_services.databases.database_status import is_active_or_raise_if_creation_failed
from redis_enterprise_services.exceptions.cluster import (
    ClusterRejectedRequestError,
    DatabaseActivationTimeoutError,
    DatabaseDeletionTimeoutError,
)
from redis_enterprise_services.resources.models import CreatedResource
from redis_enterprise_services.resources.resource_completion_waiter import ResourceCompletionWaiter

logger: logging.Logger = logging.getLogger(name=__name__)


class PollingDatabaseWaiter(DatabaseActivationWaiter, ResourceCompletionWaiter):
    def __init__(
        self,
        *,
        fields_reader: DatabaseFieldsReader,
        read_again_polling: ReadAgainPolling,
        settings: DatabaseSettings,
        cluster_api_settings: ClusterApiSettings,
    ) -> None:
        self._fields_reader: DatabaseFieldsReader = fields_reader
        self._read_again_polling: ReadAgainPolling = read_again_polling
        self._settings: DatabaseSettings = settings
        self._cluster_api_settings: ClusterApiSettings = cluster_api_settings

    def wait_until_active(self, *, target: ClusterTarget, uid: int) -> None:
        if self._poll_until(
            is_done=lambda: self._read_whether_active_or_raise_if_failed(target=target, uid=uid), uid=uid
        ):
            return
        raise DatabaseActivationTimeoutError(
            message=f"database {uid} is not {self._settings.active_status} "
            f"after {self._settings.wait.timeout_seconds} seconds"
        )

    def wait_for_pending_creation(self, *, target: ClusterTarget, resource: CreatedResource) -> None:
        self.wait_until_active(target=target, uid=resource.uid)

    def wait_for_pending_deletion(self, *, target: ClusterTarget, uid: int, action_uid: str | None) -> None:
        if self._poll_until(is_done=lambda: self._read_whether_deleted(target=target, uid=uid), uid=uid):
            return
        raise DatabaseDeletionTimeoutError(
            message=f"database {uid} still exists after {self._settings.wait.timeout_seconds} seconds"
        )

    def _poll_until(self, *, is_done: Callable[[], bool], uid: int) -> bool:
        return self._read_again_polling.poll_until(
            is_done=is_done, wait=self._settings.wait, subject=f"database {uid}"
        )

    def _read_whether_deleted(self, *, target: ClusterTarget, uid: int) -> bool:
        try:
            self._fields_reader.read_fields(
                target=target, uid=uid, field_names=[self._cluster_api_settings.fields.status]
            )
        except ClusterRejectedRequestError as error:
            if is_not_found(error=error):
                return True
            raise
        return False

    def _read_whether_active_or_raise_if_failed(self, *, target: ClusterTarget, uid: int) -> bool:
        status_field: str = self._cluster_api_settings.fields.status
        values: dict[str, JsonValue] = self._fields_reader.read_fields(
            target=target, uid=uid, field_names=[status_field]
        ).values
        status: str = required_string_field(
            body=values, name=status_field, missing_message=f"database {uid} answered without {status_field}"
        )
        logger.debug(msg=f"database {uid} is {status}")
        return is_active_or_raise_if_creation_failed(uid=uid, status=status, settings=self._settings)
