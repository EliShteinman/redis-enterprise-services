import logging

from redis_enterprise_services.cluster.credentials import ClusterCredentialsProvider
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.clusters_settings import ClusterEntry
from redis_enterprise_services.exceptions.planning import NameTakenError
from redis_enterprise_services.planning.availability.name_lookups import NameLookups
from redis_enterprise_services.planning.availability.requested_name import NameKind, RequestedName
from redis_enterprise_services.planning.availability.taken_name import TakenName
from redis_enterprise_services.planning.cluster_address import address_of

logger: logging.Logger = logging.getLogger(name=__name__)


class NameAvailability:
    def __init__(self, *, lookups: NameLookups, credentials: ClusterCredentialsProvider) -> None:
        self._lookups: NameLookups = lookups
        self._credentials: ClusterCredentialsProvider = credentials

    def taken(self, *, clusters: list[ClusterEntry], names: list[RequestedName]) -> list[TakenName]:
        by_kind: dict[NameKind, set[str]] = names_by_kind(names=names)
        return [taken for cluster in clusters for taken in self._taken_on(cluster=cluster, by_kind=by_kind)]

    def ensure_free(self, *, clusters: list[ClusterEntry], names: list[RequestedName]) -> None:
        taken: list[TakenName] = self.taken(clusters=clusters, names=names)
        if taken:
            message: str = "; ".join(name.describe() for name in taken)
            logger.warning(msg=message)
            raise NameTakenError(message=message)
        logger.info(msg=f"{len(names)} names are free on {[cluster.name for cluster in clusters]}")

    def _taken_on(self, *, cluster: ClusterEntry, by_kind: dict[NameKind, set[str]]) -> list[TakenName]:
        target: ClusterTarget = self._credentials.target_for(address=address_of(cluster=cluster))
        return [
            TakenName(kind=kind, name=name, cluster=cluster.name)
            for kind, requested in by_kind.items()
            for name in sorted(self._lookups.for_kind(kind=kind).existing(target=target, names=requested))
        ]


def names_by_kind(*, names: list[RequestedName]) -> dict[NameKind, set[str]]:
    by_kind: dict[NameKind, set[str]] = {}
    for requested in names:
        by_kind.setdefault(requested.kind, set()).add(requested.name)
    return by_kind
