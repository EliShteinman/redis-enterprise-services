from typing import Protocol

from pydantic import JsonValue

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.models import ClusterObject, CreatedResource, DeletionStarted


class ResourceEndpoint(Protocol):
    def start_creation(
        self, *, target: ClusterTarget, creation_body: dict[str, JsonValue]
    ) -> CreatedResource: ...

    def start_deletion(self, *, target: ClusterTarget, uid: int) -> DeletionStarted: ...

    def read_item(self, *, target: ClusterTarget, uid: int) -> CreatedResource: ...

    def list_objects(self, *, target: ClusterTarget) -> list[ClusterObject]: ...
