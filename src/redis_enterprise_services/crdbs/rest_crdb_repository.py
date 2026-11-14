from pydantic import ConfigDict, JsonValue, TypeAdapter

from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.cluster_body import parse_cluster_body
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster_access.http_method import HttpMethod
from redis_enterprise_services.config.crdb_settings import CrdbSettings
from redis_enterprise_services.crdbs.creation_body import crdb_creation_body
from redis_enterprise_services.crdbs.models import Crdb, NamedCrdb, instances_change
from redis_enterprise_services.crdbs.repository import CrdbRepository
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.exceptions.cluster import UnreadableClusterResponseError
from redis_enterprise_services.resources.creation_body_builder import CreationBodyBuilder

CRDB: TypeAdapter[Crdb] = TypeAdapter(Crdb)
NAMED_CRDB_LIST: TypeAdapter[list[NamedCrdb]] = TypeAdapter(
    list[NamedCrdb], config=ConfigDict(hide_input_in_errors=True)
)
CRDB_LIST: TypeAdapter[list[Crdb]] = TypeAdapter(list[Crdb], config=ConfigDict(hide_input_in_errors=True))


class RestCrdbRepository(CrdbRepository):
    def __init__(
        self,
        *,
        cluster_api_caller: ClusterApiCaller,
        database_body_builder: CreationBodyBuilder[NewDatabase],
        settings: CrdbSettings,
    ) -> None:
        self._cluster_api_caller: ClusterApiCaller = cluster_api_caller
        self._database_body_builder: CreationBodyBuilder[NewDatabase] = database_body_builder
        self._settings: CrdbSettings = settings

    def start_creation(
        self, *, coordinator: ClusterTarget, members: list[ClusterTarget], database: NewDatabase, task_id: str
    ) -> None:
        self._send_task(
            target=coordinator,
            method="POST",
            path=self._settings.collection_path,
            body=crdb_creation_body(
                name=database.name,
                default_db_config=self._database_body_builder.creation_body(spec=database),
                members=members,
                settings=self._settings.creation,
            ).model_dump(mode="json"),
            task_id=task_id,
        )

    def read(self, *, target: ClusterTarget, guid: str) -> Crdb:
        body: JsonValue = self._cluster_api_caller.send(
            target=target, method="GET", path=self._item_path(guid=guid)
        ).body
        return parse_cluster_body(
            body=body, adapter=CRDB, message_prefix=f"CRDB {guid} came back unreadable at"
        )

    def list_crdbs(self, *, target: ClusterTarget) -> list[Crdb]:
        return parse_cluster_body(
            body=self._listed(target=target),
            adapter=CRDB_LIST,
            message_prefix="the CRDB list came back unreadable at",
        )

    def list_crdb_names(self, *, target: ClusterTarget) -> set[str]:
        named: list[NamedCrdb] = parse_cluster_body(
            body=self._listed(target=target),
            adapter=NAMED_CRDB_LIST,
            message_prefix="the CRDB list came back without readable names at",
        )
        return {crdb.name for crdb in named}

    def _listed(self, *, target: ClusterTarget) -> JsonValue:
        body: JsonValue = self._cluster_api_caller.send(
            target=target, method="GET", path=self._settings.collection_path
        ).body
        if not isinstance(body, dict) or self._settings.list_field not in body:
            raise UnreadableClusterResponseError(
                message=f"the CRDB list came back without {self._settings.list_field}"
            )
        return body[self._settings.list_field]

    def start_update(
        self, *, target: ClusterTarget, guid: str, changes: dict[str, JsonValue], task_id: str
    ) -> None:
        self._send_task(
            target=target, method="PATCH", path=self._item_path(guid=guid), body=changes, task_id=task_id
        )

    def start_instances_update(
        self,
        *,
        target: ClusterTarget,
        guid: str,
        values_by_instance: dict[int, dict[str, JsonValue]],
        task_id: str,
    ) -> None:
        self.start_update(
            target=target,
            guid=guid,
            changes=instances_change(values_by_instance=values_by_instance).model_dump(mode="json"),
            task_id=task_id,
        )

    def start_deletion(self, *, target: ClusterTarget, guid: str, task_id: str) -> None:
        self._send_task(
            target=target, method="DELETE", path=self._item_path(guid=guid), body=None, task_id=task_id
        )

    def _send_task(
        self, *, target: ClusterTarget, method: HttpMethod, path: str, body: JsonValue | None, task_id: str
    ) -> None:
        self._cluster_api_caller.send(
            target=target,
            method=method,
            path=path,
            body=body,
            crdb_task_id=task_id,
            result_ttl_seconds=self._settings.task.result_ttl_seconds,
        )

    def _item_path(self, *, guid: str) -> str:
        return self._settings.item_path.format(uid=guid)
