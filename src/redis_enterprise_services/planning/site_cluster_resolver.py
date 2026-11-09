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
        candidates: list[ConfiguredCluster] = self._directory.candidates_for(placement=placement)
        raise_if_no_candidates(placement=placement, candidates=candidates)
        chosen: ConfiguredCluster = self._chooser.choose(placement=placement, candidates=candidates)
        logger.info(msg=f"{placement.describe()} resolves to cluster {chosen.name}")
        return chosen


def raise_if_no_candidates(*, placement: SitePlacement, candidates: list[ConfiguredCluster]) -> None:
    if candidates:
        return
    message: str = f"no cluster is configured for {placement.describe()}"
    logger.warning(msg=message)
    raise NoMatchingClusterError(message=message)
