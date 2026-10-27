import logging
from urllib.parse import urlencode

from pydantic import JsonValue

from redis_enterprise_services.cluster.api import ClusterApi
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster.polling import poll_until
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.databases.models import DatabaseFields
from redis_enterprise_services.edge.models import ClusterResponse
from redis_enterprise_services.exceptions.cluster import DatabaseNotActiveError

FIELDS_SEPARATOR: str = ","
STATUS_FIELD: str = "status"

logger: logging.Logger = logging.getLogger(name=__name__)


class DatabaseRepository:
    def __init__(self, *, api: ClusterApi, settings: DatabaseSettings) -> None:
        self._api: ClusterApi = api
        self._settings: DatabaseSettings = settings

    def get_fields(self, *, target: ClusterTarget, uid: int, fields: list[str]) -> DatabaseFields:
        query: str = urlencode(query={"fields": FIELDS_SEPARATOR.join(fields)}, safe=FIELDS_SEPARATOR)
        response: ClusterResponse = self._api.send(
            target=target, method="GET", path=self._settings.path.format(uid=uid), query=query
        )
        return DatabaseFields(values=response.body, cluster_state_id=response.cluster_state_id)

    def update(
        self, *, target: ClusterTarget, uid: int, values: dict[str, JsonValue], cluster_state_id: int
    ) -> None:
        logger.info(msg=f"updating {sorted(values)} of database {uid}")
        self._api.send(
            target=target,
            method="PUT",
            path=self._settings.path.format(uid=uid),
            body=values,
            cluster_state_id=cluster_state_id,
        )

    def wait_until_active(self, *, target: ClusterTarget, uid: int) -> None:
        if poll_until(wait=self._settings.wait, is_done=lambda: self._is_active(target=target, uid=uid)):
            return
        raise DatabaseNotActiveError(
            message=f"database {uid} is not {self._settings.active_status} "
            f"after {self._settings.wait.timeout_seconds} seconds"
        )

    def _is_active(self, *, target: ClusterTarget, uid: int) -> bool:
        status: JsonValue = self.get_fields(target=target, uid=uid, fields=[STATUS_FIELD]).values.get(
            STATUS_FIELD
        )
        logger.debug(msg=f"database {uid} is {status}")
        return status == self._settings.active_status
