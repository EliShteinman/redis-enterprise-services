import logging

from pydantic import ConfigDict, JsonValue, TypeAdapter, ValidationError

from redis_enterprise_services.cluster.api import ClusterApi
from redis_enterprise_services.cluster.json_body import failed_fields, string_field
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.cluster_settings import ClusterSettings
from redis_enterprise_services.config.resource_settings import ResourceSettings
from redis_enterprise_services.exceptions.cluster import UnreadableAnswerError
from redis_enterprise_services.resources.models import CreatedResource, NamedResource

NAMED_RESOURCE_LIST: TypeAdapter[list[NamedResource]] = TypeAdapter(
    type=list[NamedResource], config=ConfigDict(hide_input_in_errors=True)
)

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
        try:
            resource: NamedResource = NamedResource.model_validate(obj=answer)
        except ValidationError as error:
            raise UnreadableAnswerError(
                message=f"created {body.get('name')}, unreadable answer fields {failed_fields(error=error)}"
            ) from error
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
        try:
            resources: list[NamedResource] = NAMED_RESOURCE_LIST.validate_python(answer)
        except ValidationError as error:
            raise UnreadableAnswerError(
                message=f"cannot read {self._settings.collection_path}, fields {failed_fields(error=error)}"
            ) from error
        return [resource for resource in resources if resource.name == name]

    def _action_uid(self, *, body: JsonValue) -> str | None:
        return string_field(body=body, name=self._cluster.fields.action_uid)
