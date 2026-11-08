import logging

from redis_enterprise_services.config.cluster_inventory import ClusterEntry
from redis_enterprise_services.exceptions.planning import UnknownClusterError
from redis_enterprise_services.planning.cluster_chooser import ClusterChooser
from redis_enterprise_services.planning.cluster_directory import ClusterDirectory
from redis_enterprise_services.planning.site_target import SiteTarget

logger: logging.Logger = logging.getLogger(name=__name__)


class ClusterResolver:
    def __init__(self, *, directory: ClusterDirectory, chooser: ClusterChooser) -> None:
        self._directory: ClusterDirectory = directory
        self._chooser: ClusterChooser = chooser

    def resolve(self, *, target: SiteTarget) -> ClusterEntry:
        candidates: list[ClusterEntry] = self._candidates(target=target)
        if not candidates:
            message: str = f"no cluster is configured for {target.describe()}"
            logger.warning(msg=message)
            raise UnknownClusterError(message=message)
        chosen: ClusterEntry = (
            self._chooser.choose(target=target, candidates=candidates)
            if target.cluster.type == "generic"
            else candidates[0]
        )
        logger.info(msg=f"{target.describe()} resolves to cluster {chosen.name}")
        return chosen

    def _candidates(self, *, target: SiteTarget) -> list[ClusterEntry]:
        at_site: list[ClusterEntry] = self._directory.at_site(target=target, cluster_type=target.cluster.type)
        if target.cluster.type == "generic":
            return at_site
        return [cluster for cluster in at_site if cluster.name == target.cluster.name]
