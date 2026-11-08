import logging

from pydantic import ConfigDict, JsonValue, TypeAdapter

from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.cluster_body import parse_cluster_body
from redis_enterprise_services.cluster.fields_query_string import fields_query_string
from redis_enterprise_services.cluster.json_body import string_field
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.config.resource_settings import ResourceSettings
from redis_enterprise_services.resources.models import CreatedResource, NamedResource
from redis_enterprise_services.resources.resource_endpoint import ResourceEndpoint

NAMED_RESOURCE_LIST_ADAPTER: TypeAdapter[list[NamedResource]] = TypeAdapter(
    type=list[NamedResource], config=ConfigDict(hide_input_in_errors=True)
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
        logger.info(msg=f"creating {self._settings.collection_path} {creation_body.get('name')}")
        response_body: JsonValue = self._cluster_api_caller.send(
            target=target, method="POST", path=self._settings.collection_path, body=creation_body
        ).body
        return created_resource(
            response_body=response_body,
            requested_name=creation_body.get("name"),
            action_uid=self._action_uid(response_body=response_body),
        )

    def start_deletion(self, *, target: ClusterTarget, uid: int) -> str | None:
        logger.info(msg=f"deleting {self._settings.item_path.format(uid=uid)}")
        response_body: JsonValue = self._cluster_api_caller.send(
            target=target, method="DELETE", path=self._settings.item_path.format(uid=uid)
        ).body
        return self._action_uid(response_body=response_body)

    def list_uids_and_names(self, *, target: ClusterTarget) -> list[NamedResource]:
        response_body: JsonValue = self._cluster_api_caller.send(
            target=target,
            method="GET",
            path=self._settings.collection_path,
            query_string=self._list_fields_query_string(),
        ).body
        return parse_cluster_body(
            body=response_body,
            adapter=NAMED_RESOURCE_LIST_ADAPTER,
            message_prefix=f"cannot read {self._settings.collection_path}, fields",
        )

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
        message_prefix=f"created {requested_name}, unreadable response fields",
    )
    return CreatedResource(uid=resource.uid, name=resource.name, action_uid=action_uid)
