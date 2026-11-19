from typing import Protocol

from redis_enterprise_services.cluster.models import ClusterTarget


class NameLookup(Protocol):
    def find_existing(self, *, target: ClusterTarget, names: set[str]) -> set[str]: ...
