from typing import Protocol

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.planning.site_placement import SitePlacement


class ClusterChooser(Protocol):
    def choose(
        self, *, placement: SitePlacement, candidates: list[ConfiguredCluster]
    ) -> ConfiguredCluster: ...
