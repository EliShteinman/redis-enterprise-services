from typing import Protocol

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.models import ClusterObject, CreatedResource, DeletionStarted
from redis_enterprise_services.resources.named_spec import NamedSpec


class ResourceRepository[TSpec: NamedSpec](Protocol):
    def start_creation(self, *, target: ClusterTarget, spec: TSpec) -> CreatedResource: ...

    def start_deletion(self, *, target: ClusterTarget, uid: int) -> DeletionStarted: ...

    def find_by_name(self, *, target: ClusterTarget, name: str) -> list[ClusterObject]: ...

    def read_created(self, *, target: ClusterTarget, uid: int) -> CreatedResource: ...

    def missing_fields(self, *, spec: TSpec, created: CreatedResource) -> list[str]: ...
