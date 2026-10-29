import logging

from redis_enterprise_services.config.clusters_settings import ClusterEntry
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.planning.cluster_chooser import ClusterChooser
from redis_enterprise_services.planning.site_target import SiteTarget

logger: logging.Logger = logging.getLogger(name=__name__)


class SingleCandidateChooser(ClusterChooser):
    def choose(self, *, target: SiteTarget, candidates: list[ClusterEntry]) -> ClusterEntry:
        if len(candidates) > 1:
            names: list[str] = [candidate.name for candidate in candidates]
            message: str = f"{target.describe()} has several generic clusters {names}, and no way to choose"
            logger.error(msg=message)
            raise ConfigurationError(message=message)
        return candidates[0]
