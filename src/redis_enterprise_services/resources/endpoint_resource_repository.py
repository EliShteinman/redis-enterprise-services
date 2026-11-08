from pydantic import JsonValue

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.models import CreatedResource, NamedResource
from redis_enterprise_services.resources.named_spec import NamedSpec
from redis_enterprise_services.resources.repository import ResourceRepository
from redis_enterprise_services.resources.resource_endpoint import ResourceEndpoint
from redis_enterprise_services.resources.resource_name_lister import ResourceNameLister


class EndpointResourceRepository[TSpec: NamedSpec](ResourceRepository[TSpec], ResourceNameLister):
    def __init__(self, *, endpoint: ResourceEndpoint) -> None:
        self._endpoint: ResourceEndpoint = endpoint

    def start_creation(self, *, target: ClusterTarget, spec: TSpec) -> CreatedResource:
        return self._endpoint.start_creation(target=target, body=self.creation_body(spec=spec))

    def start_deletion(self, *, target: ClusterTarget, uid: int) -> str | None:
        return self._endpoint.start_deletion(target=target, uid=uid)

    def find_by_name(self, *, target: ClusterTarget, name: str) -> list[NamedResource]:
        return self._endpoint.find_by_name(target=target, name=name)

    def list_uids_and_names(self, *, target: ClusterTarget) -> list[NamedResource]:
        return self._endpoint.list_uids_and_names(target=target)

    def creation_body(self, *, spec: TSpec) -> dict[str, JsonValue]:
        return spec.model_dump()
