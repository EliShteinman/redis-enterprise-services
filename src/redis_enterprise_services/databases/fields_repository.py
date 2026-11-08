import logging

from pydantic import JsonValue, ValidationError

from redis_enterprise_services.cluster.caller import ClusterCaller
from redis_enterprise_services.cluster.fields_query import fields_query
from redis_enterprise_services.cluster.json_body import failed_fields
from redis_enterprise_services.cluster.models import ClusterAnswer, ClusterTarget
from redis_enterprise_services.config.cluster_settings import ClusterSettings
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.databases.fields_store import DatabaseFieldsStore
from redis_enterprise_services.databases.models import DatabaseFields
from redis_enterprise_services.exceptions.cluster import UnreadableAnswerError

logger: logging.Logger = logging.getLogger(name=__name__)


class DatabaseFieldsRepository(DatabaseFieldsStore):
    def __init__(self, *, api: ClusterCaller, settings: DatabaseSettings, cluster: ClusterSettings) -> None:
        self._api: ClusterCaller = api
        self._settings: DatabaseSettings = settings
        self._cluster: ClusterSettings = cluster

    def get_fields(self, *, target: ClusterTarget, uid: int, fields: list[str]) -> DatabaseFields:
        response: ClusterAnswer = self._api.send(
            target=target,
            method="GET",
            path=self._settings.path.format(uid=uid),
            query=self._query(fields=fields),
        )
        try:
            return DatabaseFields.model_validate(
                obj={"values": response.body, "cluster_state_id": response.cluster_state_id}
            )
        except ValidationError as error:
            raise UnreadableAnswerError(
                message=f"database {uid} answered with unreadable fields {failed_fields(error=error)}"
            ) from error

    def _query(self, *, fields: list[str]) -> str:
        return fields_query(settings=self._cluster.fields_query, fields=fields)

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
