import logging

from pydantic import JsonValue, TypeAdapter

from redis_enterprise_services.cluster.api import ClusterApi
from redis_enterprise_services.cluster.json_body import string_field
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.cluster_settings import ClusterSettings
from redis_enterprise_services.config.resource_settings import ResourceSettings
from redis_enterprise_services.resources.models import CreatedResource, NamedResource

NAMED_RESOURCE_LIST: TypeAdapter[list[NamedResource]] = TypeAdapter(type=list[NamedResource])

logger: logging.Logger = logging.getLogger(name=__name__)


class ResourceEndpoint:
    def __init__(self, *, api: ClusterApi, settings: ResourceSettings, cluster: ClusterSettings) -> None:
        self._api: ClusterApi = api
        self._settings: ResourceSettings = settings
        self._cluster: ClusterSettings = cluster

    def create(self, *, target: ClusterTarget, body: dict[str, JsonValue]) -> CreatedResource:
        logger.info(msg=f"creating {self._settings.collection_path} {body.get('name')}")
        answer: JsonValue = self._api.send(
            target=target, method="POST", path=self._settings.collection_path, body=body
        ).body
        resource: NamedResource = NamedResource.model_validate(obj=answer)
        return CreatedResource(uid=resource.uid, name=resource.name, action_uid=self._action_uid(body=answer))

    def delete(self, *, target: ClusterTarget, uid: int) -> str | None:
        logger.info(msg=f"deleting {self._settings.path.format(uid=uid)}")
        answer: JsonValue = self._api.send(
            target=target, method="DELETE", path=self._settings.path.format(uid=uid)
        ).body
        return self._action_uid(body=answer)

    def find_by_name(self, *, target: ClusterTarget, name: str) -> list[NamedResource]:
        answer: JsonValue = self._api.send(
            target=target, method="GET", path=self._settings.collection_path
        ).body
        return [resource for resource in NAMED_RESOURCE_LIST.validate_python(answer) if resource.name == name]

    def _action_uid(self, *, body: JsonValue) -> str | None:
        return string_field(body=body, name=self._cluster.fields.action_uid)
