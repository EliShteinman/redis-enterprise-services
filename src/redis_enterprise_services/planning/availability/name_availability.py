import logging

from redis_enterprise_services.cluster.credentials import ClusterCredentialsProvider
from redis_enterprise_services.cluster.models import ClusterAddress, ClusterTarget
from redis_enterprise_services.config.clusters_settings import ClusterEntry
from redis_enterprise_services.exceptions.planning import NameTakenError
from redis_enterprise_services.planning.availability.name_lookup import NameLookup
from redis_enterprise_services.planning.availability.requested_name import NameKind, RequestedName
from redis_enterprise_services.planning.availability.taken_name import TakenName

logger: logging.Logger = logging.getLogger(name=__name__)


class NameAvailability:
    def __init__(
        self, *, lookups: dict[NameKind, NameLookup], credentials: ClusterCredentialsProvider
    ) -> None:
        self._lookups: dict[NameKind, NameLookup] = lookups
        self._credentials: ClusterCredentialsProvider = credentials

    def taken(self, *, clusters: list[ClusterEntry], names: list[RequestedName]) -> list[TakenName]:
        return [
            TakenName(kind=requested.kind, name=requested.name, cluster=cluster.name)
            for cluster in clusters
            for requested in names
            if self._lookups[requested.kind].exists(target=self._target(cluster=cluster), name=requested.name)
        ]

    def ensure_free(self, *, clusters: list[ClusterEntry], names: list[RequestedName]) -> None:
        taken: list[TakenName] = self.taken(clusters=clusters, names=names)
        if taken:
            message: str = "; ".join(name.describe() for name in taken)
            logger.warning(msg=message)
            raise NameTakenError(message=message)
        logger.info(msg=f"{len(names)} names are free on {[cluster.name for cluster in clusters]}")

    def _target(self, *, cluster: ClusterEntry) -> ClusterTarget:
        return self._credentials.target_for(
            address=ClusterAddress(network=cluster.network, api_url=cluster.api_url)
        )
