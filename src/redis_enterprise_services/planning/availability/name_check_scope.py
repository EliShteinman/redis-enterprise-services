from typing import Protocol

from redis_enterprise_services.config.cluster_inventory import ClusterEntry


class NameCheckScope(Protocol):
    def clusters_to_check(self, *, chosen: ClusterEntry) -> list[ClusterEntry]: ...
