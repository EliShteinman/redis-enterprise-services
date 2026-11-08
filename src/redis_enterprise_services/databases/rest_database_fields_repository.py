import logging

from pydantic import JsonValue, ValidationError

from redis_enterprise_services.cluster.api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.fields_query import fields_query
from redis_enterprise_services.cluster.invalid_field_paths import invalid_field_paths
from redis_enterprise_services.cluster.models import ClusterTarget, SuccessfulClusterResponse
from redis_enterprise_services.config.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.databases.database_fields_repository import DatabaseFieldsRepository
from redis_enterprise_services.databases.models import DatabaseFields
from redis_enterprise_services.exceptions.cluster import UnreadableClusterResponseError

logger: logging.Logger = logging.getLogger(name=__name__)


class RestDatabaseFieldsRepository(DatabaseFieldsRepository):
    def __init__(
        self, *, api: ClusterApiCaller, settings: DatabaseSettings, cluster_api: ClusterApiSettings
    ) -> None:
        self._api: ClusterApiCaller = api
        self._settings: DatabaseSettings = settings
        self._cluster_api: ClusterApiSettings = cluster_api

    def get_fields(self, *, target: ClusterTarget, uid: int, field_names: list[str]) -> DatabaseFields:
        response: SuccessfulClusterResponse = self._api.send(
            target=target,
            method="GET",
            path=self._settings.path.format(uid=uid),
            query=self._fields_query_string(field_names=field_names),
        )
        try:
            return DatabaseFields.model_validate(
                obj={"values": response.body, "cluster_state_id": response.cluster_state_id}
            )
        except ValidationError as error:
            raise UnreadableClusterResponseError(
                message=f"database {uid} answered with unreadable fields {invalid_field_paths(error=error)}"
            ) from error

    def _fields_query_string(self, *, field_names: list[str]) -> str:
        return fields_query(settings=self._cluster_api.fields_query, fields=field_names)

    def update_fields(
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
