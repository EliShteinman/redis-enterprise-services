import logging

from pydantic import JsonValue

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster.polling import poll_until
from redis_enterprise_services.config.cluster_settings import ClusterSettings
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.databases.fields_store import DatabaseFieldsReader
from redis_enterprise_services.databases.readiness import DatabaseReadiness
from redis_enterprise_services.exceptions.cluster import DatabaseNotActiveError

logger: logging.Logger = logging.getLogger(name=__name__)


class DatabaseActiveWaiter(DatabaseReadiness):
    def __init__(
        self, *, fields: DatabaseFieldsReader, settings: DatabaseSettings, cluster: ClusterSettings
    ) -> None:
        self._fields: DatabaseFieldsReader = fields
        self._settings: DatabaseSettings = settings
        self._cluster: ClusterSettings = cluster

    def wait(self, *, target: ClusterTarget, uid: int) -> None:
        if poll_until(wait=self._settings.wait, is_done=lambda: self._is_active(target=target, uid=uid)):
            return
        raise DatabaseNotActiveError(
            message=f"database {uid} is not {self._settings.active_status} "
            f"after {self._settings.wait.timeout_seconds} seconds"
        )

    def _is_active(self, *, target: ClusterTarget, uid: int) -> bool:
        status_field: str = self._cluster.fields.status
        values: dict[str, JsonValue] = self._fields.get_fields(
            target=target, uid=uid, fields=[status_field]
        ).values
        status: JsonValue = values[status_field]
        logger.debug(msg=f"database {uid} is {status}")
        return status == self._settings.active_status
