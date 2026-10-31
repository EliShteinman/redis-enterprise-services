from typing import Protocol

from redis_enterprise_services.cluster.models import ClusterTarget


class NameLookup(Protocol):
    def exists(self, *, target: ClusterTarget, name: str) -> bool: ...
