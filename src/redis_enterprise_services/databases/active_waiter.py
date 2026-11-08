import logging
from http import HTTPStatus

from pydantic import JsonValue

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster.polling import poll_until_done_or_timeout
from redis_enterprise_services.cluster.transient_read import worth_reading_again
from redis_enterprise_services.config.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.databases.fields_store import DatabaseFieldsReader
from redis_enterprise_services.databases.readiness import DatabaseReadiness
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.cluster import (
    ClusterRejectedRequestError,
    DatabaseActivationTimeoutError,
    DatabaseCreationFailedError,
    DatabaseDeletionTimeoutError,
    UnreadableClusterResponseError,
)
from redis_enterprise_services.resources.completion import CompletionWaiter
from redis_enterprise_services.resources.models import CreatedResource

logger: logging.Logger = logging.getLogger(name=__name__)


class DatabaseActiveWaiter(DatabaseReadiness, CompletionWaiter):
    def __init__(
        self, *, fields: DatabaseFieldsReader, settings: DatabaseSettings, cluster_api: ClusterApiSettings
    ) -> None:
        self._fields: DatabaseFieldsReader = fields
        self._settings: DatabaseSettings = settings
        self._cluster_api: ClusterApiSettings = cluster_api

    def wait(self, *, target: ClusterTarget, uid: int) -> None:
        if poll_until_done_or_timeout(
            wait_settings=self._settings.wait, is_done=lambda: self._is_active(target=target, uid=uid)
        ):
            return
        raise DatabaseActivationTimeoutError(
            message=f"database {uid} is not {self._settings.active_status} "
            f"after {self._settings.wait.timeout_seconds} seconds"
        )

    def wait_created(self, *, target: ClusterTarget, resource: CreatedResource) -> None:
        self.wait(target=target, uid=resource.uid)

    def wait_deleted(self, *, target: ClusterTarget, uid: int, action_uid: str | None) -> None:
        if poll_until_done_or_timeout(
            wait_settings=self._settings.wait, is_done=lambda: self._is_gone(target=target, uid=uid)
        ):
            return
        raise DatabaseDeletionTimeoutError(
            message=f"database {uid} still exists after {self._settings.wait.timeout_seconds} seconds"
        )

    def _is_gone(self, *, target: ClusterTarget, uid: int) -> bool:
        try:
            self._fields.get_fields(target=target, uid=uid, fields=[self._cluster_api.fields.status])
        except ClusterRejectedRequestError as error:
            if error.cluster_status_code == HTTPStatus.NOT_FOUND:
                return True
            return self._read_again_or_raise(uid=uid, error=error)
        except RedisEnterpriseServicesError as error:
            return self._read_again_or_raise(uid=uid, error=error)
        return False

    def _read_again_or_raise(self, *, uid: int, error: RedisEnterpriseServicesError) -> bool:
        if not worth_reading_again(error=error, transient_codes=self._cluster_api.transient_error_codes):
            raise error
        logger.warning(msg=f"reading database {uid} failed, it is read again: {error.coded_message()}")
        return False

    def _is_active(self, *, target: ClusterTarget, uid: int) -> bool:
        status_field: str = self._cluster_api.fields.status
        try:
            values: dict[str, JsonValue] = self._fields.get_fields(
                target=target, uid=uid, fields=[status_field]
            ).values
        except RedisEnterpriseServicesError as error:
            return self._read_again_or_raise(uid=uid, error=error)
        status: JsonValue = values.get(status_field)
        if status is None:
            raise UnreadableClusterResponseError(message=f"database {uid} answered without {status_field}")
        logger.debug(msg=f"database {uid} is {status}")
        if status == self._settings.creation_failed_status:
            raise DatabaseCreationFailedError(message=f"database {uid} is {status}")
        return status == self._settings.active_status
