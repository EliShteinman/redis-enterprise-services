import logging

from pydantic import JsonValue, TypeAdapter

from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.cluster_body import parse_cluster_body
from redis_enterprise_services.cluster.models import ClusterTarget, SuccessfulClusterResponse
from redis_enterprise_services.config.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.databases.database_fields_repository import DatabaseFieldsRepository
from redis_enterprise_services.databases.models import DatabaseFieldsSnapshot
from redis_enterprise_services.resources.cluster_object_body import object_body

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

    def read(self, *, target: ClusterTarget, uid: int) -> DatabaseFieldsSnapshot:
        response: SuccessfulClusterResponse = self._cluster_api_caller.send(
            target=target, method="GET", path=self._settings.item_path.format(uid=uid)
        )
        return fields_snapshot(response=response, uid=uid)

    def update_fields_if_state_unchanged(
        self, *, target: ClusterTarget, uid: int, values: dict[str, JsonValue], cluster_state_id: int
    ) -> dict[str, JsonValue]:
        logger.info(msg=f"updating {sorted(values)} of database {uid}")
        response_body: JsonValue = self._cluster_api_caller.send(
            target=target,
            method="PUT",
            path=self._settings.item_path.format(uid=uid),
            body=values,
            cluster_state_id=cluster_state_id,
        ).body
        return object_body(body=response_body, message_prefix=f"updated database {uid}, unreadable answer")


def fields_snapshot(*, response: SuccessfulClusterResponse, uid: int) -> DatabaseFieldsSnapshot:
    return parse_cluster_body(
        body={"values": response.body, "cluster_state_id": response.cluster_state_id},
        adapter=DATABASE_FIELDS_SNAPSHOT_ADAPTER,
        message_prefix=f"database {uid} answered with unreadable fields",
    )
