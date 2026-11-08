from typing import Protocol

from pydantic import JsonValue

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.models import CreatedResource, NamedResource


class ResourceEndpoint(Protocol):
    def start_creation(self, *, target: ClusterTarget, body: dict[str, JsonValue]) -> CreatedResource: ...

    def start_deletion(self, *, target: ClusterTarget, uid: int) -> str | None: ...

    def find_by_name(self, *, target: ClusterTarget, name: str) -> list[NamedResource]: ...

    def list_uids_and_names(self, *, target: ClusterTarget) -> list[NamedResource]: ...
