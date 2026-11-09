import logging

from pydantic import ConfigDict, JsonValue, TypeAdapter

from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.cluster_body import parse_cluster_body
from redis_enterprise_services.cluster.fields_query_string import fields_query_string
from redis_enterprise_services.cluster.json_body import string_field
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.config.resource_settings import ResourceSettings
from redis_enterprise_services.resources.cluster_object_body import object_body
from redis_enterprise_services.resources.models import (
    ClusterObject,
    CreatedResource,
    DeletionStarted,
    NamedResource,
)
from redis_enterprise_services.resources.resource_endpoint import ResourceEndpoint

NAMED_RESOURCE_LIST_ADAPTER: TypeAdapter[list[NamedResource]] = TypeAdapter(
    type=list[NamedResource], config=ConfigDict(hide_input_in_errors=True)
)
OBJECT_LIST_ADAPTER: TypeAdapter[list[dict[str, JsonValue]]] = TypeAdapter(
    type=list[dict[str, JsonValue]], config=ConfigDict(hide_input_in_errors=True)
)
NAMED_RESOURCE_ADAPTER: TypeAdapter[NamedResource] = TypeAdapter(type=NamedResource)

logger: logging.Logger = logging.getLogger(name=__name__)


class RestResourceEndpoint(ResourceEndpoint):
    def __init__(
        self,
        *,
        cluster_api_caller: ClusterApiCaller,
        settings: ResourceSettings,
        cluster_api_settings: ClusterApiSettings,
    ) -> None:
        self._cluster_api_caller: ClusterApiCaller = cluster_api_caller
        self._settings: ResourceSettings = settings
        self._cluster_api_settings: ClusterApiSettings = cluster_api_settings

    def start_creation(
        self, *, target: ClusterTarget, creation_body: dict[str, JsonValue]
    ) -> CreatedResource:
        requested_name: JsonValue = creation_body.get("name")
        logger.info(msg=f"creating {self._settings.collection_path} {requested_name}")
        response_body: JsonValue = self._cluster_api_caller.send(
            target=target, method="POST", path=self._settings.collection_path, body=creation_body
        ).body
        return created_resource(
            response_body=response_body,
            requested_name=f"created {requested_name}",
            action_uid=self._action_uid(response_body=response_body),
        )

    def start_deletion(self, *, target: ClusterTarget, uid: int) -> DeletionStarted:
        logger.info(msg=f"deleting {self._settings.item_path.format(uid=uid)}")
        response_body: JsonValue = self._cluster_api_caller.send(
            target=target, method="DELETE", path=self._settings.item_path.format(uid=uid)
        ).body
        return DeletionStarted(
            action_uid=self._action_uid(response_body=response_body),
            fields=object_body(body=response_body, message_prefix=f"deleted {uid}, unreadable answer"),
        )

    def read_item(self, *, target: ClusterTarget, uid: int) -> CreatedResource:
        path: str = self._settings.item_path.format(uid=uid)
        response_body: JsonValue = self._cluster_api_caller.send(target=target, method="GET", path=path).body
        return created_resource(response_body=response_body, requested_name=f"read {path}", action_uid=None)

    def list_objects(self, *, target: ClusterTarget) -> list[ClusterObject]:
        response_body: JsonValue = self._cluster_api_caller.send(
            target=target,
            method="GET",
            path=self._settings.collection_path,
            query_string=self._list_fields_query_string(),
        ).body
        message_prefix: str = f"cannot read {self._settings.collection_path}, fields"
        named: list[NamedResource] = parse_cluster_body(
            body=response_body, adapter=NAMED_RESOURCE_LIST_ADAPTER, message_prefix=message_prefix
        )
        objects: list[dict[str, JsonValue]] = parse_cluster_body(
            body=response_body, adapter=OBJECT_LIST_ADAPTER, message_prefix=message_prefix
        )
        return [
            ClusterObject(uid=resource.uid, name=resource.name, fields=fields)
            for resource, fields in zip(named, objects, strict=True)
        ]

    def _list_fields_query_string(self) -> str | None:
        if not self._settings.list_fields:
            return None
        return fields_query_string(
            settings=self._cluster_api_settings.fields_query, field_names=self._settings.list_fields
        )

    def _action_uid(self, *, response_body: JsonValue) -> str | None:
        return string_field(body=response_body, name=self._cluster_api_settings.fields.action_uid)


def created_resource(
    *, response_body: JsonValue, requested_name: JsonValue, action_uid: str | None
) -> CreatedResource:
    resource: NamedResource = parse_cluster_body(
        body=response_body,
        adapter=NAMED_RESOURCE_ADAPTER,
        message_prefix=f"{requested_name}, unreadable response fields",
    )
    fields: dict[str, JsonValue] = object_body(
        body=response_body, message_prefix=f"{requested_name}, unreadable answer"
    )
    return CreatedResource(uid=resource.uid, name=resource.name, action_uid=action_uid, fields=fields)
