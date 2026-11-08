from typing import Protocol

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.models import CreatedResource, NamedResource
from redis_enterprise_services.resources.named_spec import NamedSpec


class ResourceRepository[TSpec: NamedSpec](Protocol):
    def start_creation(self, *, target: ClusterTarget, spec: TSpec) -> CreatedResource: ...

    def start_deletion(self, *, target: ClusterTarget, uid: int) -> str | None: ...

    def find_by_name(self, *, target: ClusterTarget, name: str) -> list[NamedResource]: ...
