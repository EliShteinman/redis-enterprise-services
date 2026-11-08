import logging

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.exceptions.planning import NoMatchingClusterError
from redis_enterprise_services.planning.cluster_chooser import ClusterChooser
from redis_enterprise_services.planning.cluster_directory import ClusterDirectory
from redis_enterprise_services.planning.site_placement import SitePlacement

logger: logging.Logger = logging.getLogger(name=__name__)


class SiteClusterResolver:
    def __init__(self, *, directory: ClusterDirectory, chooser: ClusterChooser) -> None:
        self._directory: ClusterDirectory = directory
        self._chooser: ClusterChooser = chooser

    def resolve(self, *, placement: SitePlacement) -> ConfiguredCluster:
        candidates: list[ConfiguredCluster] = self._candidates(placement=placement)
        if not candidates:
            message: str = f"no cluster is configured for {placement.describe()}"
            logger.warning(msg=message)
            raise NoMatchingClusterError(message=message)
        chosen: ConfiguredCluster = (
            self._chooser.choose(placement=placement, candidates=candidates)
            if placement.cluster.type == "generic"
            else candidates[0]
        )
        logger.info(msg=f"{placement.describe()} resolves to cluster {chosen.name}")
        return chosen

    def _candidates(self, *, placement: SitePlacement) -> list[ConfiguredCluster]:
        at_site: list[ConfiguredCluster] = self._directory.of_type_at_site(
            placement=placement, cluster_type=placement.cluster.type
        )
        if placement.cluster.type == "generic":
            return at_site
        return [cluster for cluster in at_site if cluster.name == placement.cluster.name]
