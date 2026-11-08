import logging

from pydantic import JsonValue, TypeAdapter

from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.cluster_body import parse_cluster_body
from redis_enterprise_services.cluster.fields_query_string import fields_query_string
from redis_enterprise_services.cluster.models import ClusterTarget, SuccessfulClusterResponse
from redis_enterprise_services.config.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.databases.database_fields_repository import DatabaseFieldsRepository
from redis_enterprise_services.databases.models import DatabaseFieldsSnapshot

DATABASE_FIELDS_SNAPSHOT_ADAPTER: TypeAdapter[DatabaseFieldsSnapshot] = TypeAdapter(
    type=DatabaseFieldsSnapshot
)

logger: logging.Logger = logging.getLogger(name=__name__)


class RestDatabaseFieldsRepository(DatabaseFieldsRepository):
    def __init__(
        self,
        *,
        cluster_api_caller: ClusterApiCaller,
        settings: DatabaseSettings,
        cluster_api_settings: ClusterApiSettings,
    ) -> None:
        self._cluster_api_caller: ClusterApiCaller = cluster_api_caller
        self._settings: DatabaseSettings = settings
        self._cluster_api_settings: ClusterApiSettings = cluster_api_settings

    def read_fields(
        self, *, target: ClusterTarget, uid: int, field_names: list[str]
    ) -> DatabaseFieldsSnapshot:
        response: SuccessfulClusterResponse = self._cluster_api_caller.send(
            target=target,
            method="GET",
            path=self._settings.item_path.format(uid=uid),
            query_string=self._fields_query_string(field_names=field_names),
        )
        return fields_snapshot(response=response, uid=uid)

    def _fields_query_string(self, *, field_names: list[str]) -> str:
        return fields_query_string(settings=self._cluster_api_settings.fields_query, field_names=field_names)

    def update_fields_if_state_unchanged(
        self, *, target: ClusterTarget, uid: int, values: dict[str, JsonValue], cluster_state_id: int
    ) -> None:
        logger.info(msg=f"updating {sorted(values)} of database {uid}")
        self._cluster_api_caller.send(
            target=target,
            method="PUT",
            path=self._settings.item_path.format(uid=uid),
            body=values,
            cluster_state_id=cluster_state_id,
        )


def fields_snapshot(*, response: SuccessfulClusterResponse, uid: int) -> DatabaseFieldsSnapshot:
    return parse_cluster_body(
        body={"values": response.body, "cluster_state_id": response.cluster_state_id},
        adapter=DATABASE_FIELDS_SNAPSHOT_ADAPTER,
        message_prefix=f"database {uid} answered with unreadable fields",
    )
