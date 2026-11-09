import logging

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.exceptions.planning import NoMatchingClusterError
from redis_enterprise_services.planning.site_placement import SitePlacement

logger: logging.Logger = logging.getLogger(name=__name__)


def raise_if_no_candidates(*, placement: SitePlacement, candidates: list[ConfiguredCluster]) -> None:
    if candidates:
        return
    message: str = f"no cluster is configured for {placement.describe()}"
    logger.warning(msg=message)
    raise NoMatchingClusterError(message=message)
