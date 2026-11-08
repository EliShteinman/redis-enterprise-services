import logging
from http import HTTPStatus

from pydantic import JsonValue

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster.polling import poll_until_done_or_timeout
from redis_enterprise_services.cluster.transient_read_error import is_transient_read_error
from redis_enterprise_services.config.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.databases.database_activation_waiter import DatabaseActivationWaiter
from redis_enterprise_services.databases.database_fields_repository import DatabaseFieldsReader
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.cluster import (
    ClusterRejectedRequestError,
    DatabaseActivationTimeoutError,
    DatabaseCreationFailedError,
    DatabaseDeletionTimeoutError,
    UnreadableClusterResponseError,
)
from redis_enterprise_services.resources.models import CreatedResource
from redis_enterprise_services.resources.resource_completion_waiter import ResourceCompletionWaiter

logger: logging.Logger = logging.getLogger(name=__name__)


class PollingDatabaseWaiter(DatabaseActivationWaiter, ResourceCompletionWaiter):
    def __init__(
        self,
        *,
        fields_reader: DatabaseFieldsReader,
        settings: DatabaseSettings,
        cluster_api: ClusterApiSettings,
    ) -> None:
        self._fields_reader: DatabaseFieldsReader = fields_reader
        self._settings: DatabaseSettings = settings
        self._cluster_api: ClusterApiSettings = cluster_api

    def wait_until_active(self, *, target: ClusterTarget, uid: int) -> None:
        if poll_until_done_or_timeout(
            wait_settings=self._settings.wait, is_done=lambda: self._is_active(target=target, uid=uid)
        ):
            return
        raise DatabaseActivationTimeoutError(
            message=f"database {uid} is not {self._settings.active_status} "
            f"after {self._settings.wait.timeout_seconds} seconds"
        )

    def wait_until_created(self, *, target: ClusterTarget, resource: CreatedResource) -> None:
        self.wait_until_active(target=target, uid=resource.uid)

    def wait_until_deleted(self, *, target: ClusterTarget, uid: int, action_uid: str | None) -> None:
        if poll_until_done_or_timeout(
            wait_settings=self._settings.wait, is_done=lambda: self._is_deleted(target=target, uid=uid)
        ):
            return
        raise DatabaseDeletionTimeoutError(
            message=f"database {uid} still exists after {self._settings.wait.timeout_seconds} seconds"
        )

    def _is_deleted(self, *, target: ClusterTarget, uid: int) -> bool:
        try:
            self._fields_reader.get_fields(
                target=target, uid=uid, field_names=[self._cluster_api.fields.status]
            )
        except ClusterRejectedRequestError as error:
            if error.cluster_status_code == HTTPStatus.NOT_FOUND:
                return True
            return self._raise_unless_transient(uid=uid, error=error)
        except RedisEnterpriseServicesError as error:
            return self._raise_unless_transient(uid=uid, error=error)
        return False

    def _raise_unless_transient(self, *, uid: int, error: RedisEnterpriseServicesError) -> bool:
        if not is_transient_read_error(
            error=error, transient_error_codes=self._cluster_api.transient_error_codes
        ):
            raise error
        logger.warning(msg=f"reading database {uid} failed, it is read again: {error.coded_message()}")
        return False

    def _is_active(self, *, target: ClusterTarget, uid: int) -> bool:
        status_field: str = self._cluster_api.fields.status
        try:
            values: dict[str, JsonValue] = self._fields_reader.get_fields(
                target=target, uid=uid, field_names=[status_field]
            ).values
        except RedisEnterpriseServicesError as error:
            return self._raise_unless_transient(uid=uid, error=error)
        status: JsonValue = values.get(status_field)
        if status is None:
            raise UnreadableClusterResponseError(message=f"database {uid} answered without {status_field}")
        logger.debug(msg=f"database {uid} is {status}")
        if status == self._settings.creation_failed_status:
            raise DatabaseCreationFailedError(message=f"database {uid} is {status}")
        return status == self._settings.active_status
