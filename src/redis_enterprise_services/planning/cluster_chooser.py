from typing import Protocol

from redis_enterprise_services.config.clusters_settings import ClusterEntry
from redis_enterprise_services.planning.site_target import SiteTarget


class ClusterChooser(Protocol):
    def choose(self, *, target: SiteTarget, candidates: list[ClusterEntry]) -> ClusterEntry: ...
