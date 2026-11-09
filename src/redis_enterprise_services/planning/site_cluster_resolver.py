import logging

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.planning.cluster_chooser import ClusterChooser
from redis_enterprise_services.planning.cluster_directory import ClusterDirectory
from redis_enterprise_services.planning.site_placement import SitePlacement

logger: logging.Logger = logging.getLogger(name=__name__)


class SiteClusterResolver:
    def __init__(self, *, directory: ClusterDirectory, chooser: ClusterChooser) -> None:
        self._directory: ClusterDirectory = directory
        self._chooser: ClusterChooser = chooser

    def resolve(self, *, placement: SitePlacement) -> ConfiguredCluster:
        candidates: list[ConfiguredCluster] = self._directory.candidates_for(placement=placement)
        chosen: ConfiguredCluster = self._chooser.choose(placement=placement, candidates=candidates)
        logger.info(msg=f"{placement.describe()} resolves to cluster {chosen.name}")
        return chosen
