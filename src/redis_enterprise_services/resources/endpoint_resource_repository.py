from pydantic import JsonValue

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.creation_body_builder import CreationBodyBuilder
from redis_enterprise_services.resources.models import ClusterObject, CreatedResource, DeletionStarted
from redis_enterprise_services.resources.named_spec import NamedSpec
from redis_enterprise_services.resources.repository import ResourceRepository
from redis_enterprise_services.resources.resource_endpoint import ResourceEndpoint
from redis_enterprise_services.resources.resource_name_lister import ResourceNameLister
from redis_enterprise_services.resources.resources_named import resources_named


class EndpointResourceRepository[TSpec: NamedSpec](ResourceRepository[TSpec], ResourceNameLister):
    def __init__(
        self,
        *,
        endpoint: ResourceEndpoint,
        body_builder: CreationBodyBuilder[TSpec],
        unreturned_fields: frozenset[str],
    ) -> None:
        self._endpoint: ResourceEndpoint = endpoint
        self._body_builder: CreationBodyBuilder[TSpec] = body_builder
        self._unreturned_fields: frozenset[str] = unreturned_fields

    def start_creation(self, *, target: ClusterTarget, spec: TSpec) -> CreatedResource:
        return self._endpoint.start_creation(
            target=target, creation_body=self._body_builder.creation_body(spec=spec)
        )

    def start_deletion(self, *, target: ClusterTarget, uid: int) -> DeletionStarted:
        return self._endpoint.start_deletion(target=target, uid=uid)

    def find_by_name(self, *, target: ClusterTarget, name: str) -> list[ClusterObject]:
        return resources_named(resources=self._endpoint.list_objects(target=target), name=name)

    def read_created(self, *, target: ClusterTarget, uid: int) -> CreatedResource:
        return self._endpoint.read_item(target=target, uid=uid)

    def missing_fields(self, *, spec: TSpec, created: CreatedResource) -> list[str]:
        return fields_without_value(
            sent=self._body_builder.creation_body(spec=spec),
            returned=created.fields,
            unreturned_fields=self._unreturned_fields,
        )

    def list_objects(self, *, target: ClusterTarget) -> list[ClusterObject]:
        return self._endpoint.list_objects(target=target)


def fields_without_value(
    *, sent: dict[str, JsonValue], returned: dict[str, JsonValue], unreturned_fields: frozenset[str]
) -> list[str]:
    return sorted(name for name in sent if name not in unreturned_fields and returned.get(name) is None)
