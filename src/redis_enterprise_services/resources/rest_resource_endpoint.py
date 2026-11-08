import logging

from pydantic import ConfigDict, JsonValue, TypeAdapter, ValidationError

from redis_enterprise_services.cluster.api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.fields_query import fields_query
from redis_enterprise_services.cluster.invalid_field_paths import invalid_field_paths
from redis_enterprise_services.cluster.json_body import string_field
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.config.resource_settings import ResourceSettings
from redis_enterprise_services.exceptions.cluster import UnreadableClusterResponseError
from redis_enterprise_services.resources.models import CreatedResource, NamedResource
from redis_enterprise_services.resources.resource_endpoint import ResourceEndpoint

NAMED_RESOURCE_LIST_ADAPTER: TypeAdapter[list[NamedResource]] = TypeAdapter(
    type=list[NamedResource], config=ConfigDict(hide_input_in_errors=True)
)

logger: logging.Logger = logging.getLogger(name=__name__)


class RestResourceEndpoint(ResourceEndpoint):
    def __init__(
        self, *, api: ClusterApiCaller, settings: ResourceSettings, cluster_api: ClusterApiSettings
    ) -> None:
        self._api: ClusterApiCaller = api
        self._settings: ResourceSettings = settings
        self._cluster_api: ClusterApiSettings = cluster_api

    def create(self, *, target: ClusterTarget, body: dict[str, JsonValue]) -> CreatedResource:
        logger.info(msg=f"creating {self._settings.collection_path} {body.get('name')}")
        response_body: JsonValue = self._api.send(
            target=target, method="POST", path=self._settings.collection_path, body=body
        ).body
        try:
            resource: NamedResource = NamedResource.model_validate(obj=response_body)
        except ValidationError as error:
            raise UnreadableClusterResponseError(
                message=f"created {body.get('name')}, "
                f"unreadable response fields {invalid_field_paths(error=error)}"
            ) from error
        return CreatedResource(
            uid=resource.uid, name=resource.name, action_uid=self._action_uid(body=response_body)
        )

    def delete(self, *, target: ClusterTarget, uid: int) -> str | None:
        logger.info(msg=f"deleting {self._settings.path.format(uid=uid)}")
        response_body: JsonValue = self._api.send(
            target=target, method="DELETE", path=self._settings.path.format(uid=uid)
        ).body
        return self._action_uid(body=response_body)

    def find_by_name(self, *, target: ClusterTarget, name: str) -> list[NamedResource]:
        return [resource for resource in self.list_named(target=target) if resource.name == name]

    def list_named(self, *, target: ClusterTarget) -> list[NamedResource]:
        response_body: JsonValue = self._api.send(
            target=target,
            method="GET",
            path=self._settings.collection_path,
            query=self._list_fields_query_string(),
        ).body
        try:
            return NAMED_RESOURCE_LIST_ADAPTER.validate_python(response_body)
        except ValidationError as error:
            raise UnreadableClusterResponseError(
                message=f"cannot read {self._settings.collection_path}, "
                f"fields {invalid_field_paths(error=error)}"
            ) from error

    def _list_fields_query_string(self) -> str | None:
        if not self._settings.list_fields:
            return None
        return fields_query(settings=self._cluster_api.fields_query, fields=self._settings.list_fields)

    def _action_uid(self, *, body: JsonValue) -> str | None:
        return string_field(body=body, name=self._cluster_api.fields.action_uid)
