import logging

from redis_enterprise_services.config.cluster_inventory import ClusterEntry
from redis_enterprise_services.exceptions.planning import UnknownClusterError
from redis_enterprise_services.planning.cluster_chooser import ClusterChooser
from redis_enterprise_services.planning.cluster_directory import ClusterDirectory
from redis_enterprise_services.planning.site_placement import SitePlacement

logger: logging.Logger = logging.getLogger(name=__name__)


class SiteClusterResolver:
    def __init__(self, *, directory: ClusterDirectory, chooser: ClusterChooser) -> None:
        self._directory: ClusterDirectory = directory
        self._chooser: ClusterChooser = chooser

    def resolve(self, *, site_target: SitePlacement) -> ClusterEntry:
        candidates: list[ClusterEntry] = self._candidates(site_target=site_target)
        if not candidates:
            message: str = f"no cluster is configured for {site_target.describe()}"
            logger.warning(msg=message)
            raise UnknownClusterError(message=message)
        chosen: ClusterEntry = (
            self._chooser.choose(target=site_target, candidates=candidates)
            if site_target.cluster.type == "generic"
            else candidates[0]
        )
        logger.info(msg=f"{site_target.describe()} resolves to cluster {chosen.name}")
        return chosen

    def _candidates(self, *, site_target: SitePlacement) -> list[ClusterEntry]:
        at_site: list[ClusterEntry] = self._directory.of_type_at_site(
            site_target=site_target, cluster_type=site_target.cluster.type
        )
        if site_target.cluster.type == "generic":
            return at_site
        return [cluster for cluster in at_site if cluster.name == site_target.cluster.name]
