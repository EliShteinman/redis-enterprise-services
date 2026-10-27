import logging
import time
from http import HTTPStatus
from urllib.parse import urlencode

from pydantic import JsonValue

from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.databases.models import DatabaseFields
from redis_enterprise_services.edge.client import EdgeClient
from redis_enterprise_services.edge.models import ClusterRequest, ClusterResponse, ClusterTarget, HttpMethod
from redis_enterprise_services.exceptions.cluster import ClusterRequestError, DatabaseNotActiveError

FIELDS_SEPARATOR: str = ","
STATUS_FIELD: str = "status"

logger: logging.Logger = logging.getLogger(name=__name__)


class DatabaseRepository:
    def __init__(self, *, edge_client: EdgeClient, settings: DatabaseSettings) -> None:
        self._edge_client: EdgeClient = edge_client
        self._settings: DatabaseSettings = settings

    def get_fields(self, *, target: ClusterTarget, uid: int, fields: list[str]) -> DatabaseFields:
        query: str = urlencode(query={"fields": FIELDS_SEPARATOR.join(fields)}, safe=FIELDS_SEPARATOR)
        response: ClusterResponse = self._send(target=target, method="GET", uid=uid, query=query)
        return DatabaseFields(values=response.body, cluster_state_id=response.cluster_state_id)

    def update(
        self, *, target: ClusterTarget, uid: int, values: dict[str, JsonValue], cluster_state_id: int
    ) -> None:
        logger.info(msg=f"updating {sorted(values)} of database {uid}")
        self._send(target=target, method="PUT", uid=uid, body=values, cluster_state_id=cluster_state_id)

    def wait_until_active(self, *, target: ClusterTarget, uid: int) -> None:
        deadline: float = time.monotonic() + self._settings.wait.timeout_seconds
        while time.monotonic() < deadline:
            status: JsonValue = self.get_fields(target=target, uid=uid, fields=[STATUS_FIELD]).values[
                STATUS_FIELD
            ]
            if status == self._settings.active_status:
                return
            logger.debug(msg=f"database {uid} is {status}")
            time.sleep(self._settings.wait.interval_seconds)
        raise DatabaseNotActiveError(
            message=f"database {uid} is not {self._settings.active_status} "
            f"after {self._settings.wait.timeout_seconds} seconds"
        )

    def _send(
        self,
        *,
        target: ClusterTarget,
        method: HttpMethod,
        uid: int,
        query: str | None = None,
        body: JsonValue | None = None,
        cluster_state_id: int | None = None,
    ) -> ClusterResponse:
        url: str = target.api_url + self._settings.path.format(uid=uid)
        request: ClusterRequest = ClusterRequest(
            method=method,
            url=f"{url}?{query}" if query else url,
            credentials=target.credentials,
            body=body,
            cluster_state_id=cluster_state_id,
        )
        response: ClusterResponse = self._edge_client.send(network=target.network, request=request)
        if response.status_code >= HTTPStatus.BAD_REQUEST:
            raise self._cluster_error(response=response)
        return response

    @staticmethod
    def _cluster_error(*, response: ClusterResponse) -> ClusterRequestError:
        error_code: JsonValue = response.body.get("error_code") if isinstance(response.body, dict) else None
        return ClusterRequestError(
            message=f"cluster answered {response.status_code}: {response.body}",
            cluster_status_code=response.status_code,
            error_code=error_code if isinstance(error_code, str) else None,
        )
