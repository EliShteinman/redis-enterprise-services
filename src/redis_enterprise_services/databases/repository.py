import logging
from urllib.parse import urlencode

from pydantic import JsonValue, ValidationError

from redis_enterprise_services.cluster.api import ClusterApi
from redis_enterprise_services.cluster.json_body import failed_fields
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.cluster_settings import ClusterSettings, FieldsQuerySettings
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.databases.models import DatabaseFields
from redis_enterprise_services.edge.models import ClusterResponse
from redis_enterprise_services.exceptions.cluster import UnreadableAnswerError

logger: logging.Logger = logging.getLogger(name=__name__)


class DatabaseRepository:
    def __init__(self, *, api: ClusterApi, settings: DatabaseSettings, cluster: ClusterSettings) -> None:
        self._api: ClusterApi = api
        self._settings: DatabaseSettings = settings
        self._cluster: ClusterSettings = cluster

    def get_fields(self, *, target: ClusterTarget, uid: int, fields: list[str]) -> DatabaseFields:
        fields_query: FieldsQuerySettings = self._cluster.fields_query
        query: str = urlencode(
            query={fields_query.name: fields_query.separator.join(fields)}, safe=fields_query.separator
        )
        response: ClusterResponse = self._api.send(
            target=target, method="GET", path=self._settings.path.format(uid=uid), query=query
        )
        try:
            return DatabaseFields.model_validate(
                obj={"values": response.body, "cluster_state_id": response.cluster_state_id}
            )
        except ValidationError as error:
            raise UnreadableAnswerError(
                message=f"database {uid} answered without {failed_fields(error=error)}"
            ) from error

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
