from pydantic import JsonValue

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.models import CreatedResource, NamedResource
from redis_enterprise_services.resources.named_resource_lister import NamedResourceLister
from redis_enterprise_services.resources.named_spec import NamedSpec
from redis_enterprise_services.resources.repository import ResourceRepository
from redis_enterprise_services.resources.resource_endpoint import ResourceEndpoint


class EndpointRepository[TSpec: NamedSpec](ResourceRepository[TSpec], NamedResourceLister):
    def __init__(self, *, endpoint: ResourceEndpoint) -> None:
        self._endpoint: ResourceEndpoint = endpoint

    def create(self, *, target: ClusterTarget, spec: TSpec) -> CreatedResource:
        return self._endpoint.create(target=target, body=self.creation_body(spec=spec))

    def delete(self, *, target: ClusterTarget, uid: int) -> str | None:
        return self._endpoint.delete(target=target, uid=uid)

    def find_by_name(self, *, target: ClusterTarget, name: str) -> list[NamedResource]:
        return self._endpoint.find_by_name(target=target, name=name)

    def list_named(self, *, target: ClusterTarget) -> list[NamedResource]:
        return self._endpoint.list_named(target=target)

    def creation_body(self, *, spec: TSpec) -> dict[str, JsonValue]:
        return spec.model_dump()
