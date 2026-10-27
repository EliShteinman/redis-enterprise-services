from typing import Protocol

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.models import CreatedResource, NamedResource
from redis_enterprise_services.resources.spec import NamedSpec


class ResourceRepository[TSpec: NamedSpec](Protocol):
    def create(self, *, target: ClusterTarget, spec: TSpec) -> CreatedResource: ...

    def delete(self, *, target: ClusterTarget, uid: int) -> str | None: ...

    def find_by_name(self, *, target: ClusterTarget, name: str) -> NamedResource | None: ...
