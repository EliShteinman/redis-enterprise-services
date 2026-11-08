import logging

from redis_enterprise_services.cluster.cluster_target_resolver import ClusterTargetResolver
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.cluster_inventory import ClusterEntry
from redis_enterprise_services.exceptions.planning import NameTakenError
from redis_enterprise_services.planning.availability.name_lookups_by_kind import NameLookupsByKind
from redis_enterprise_services.planning.availability.requested_name import NameKind, RequestedName
from redis_enterprise_services.planning.availability.taken_name import TakenName
from redis_enterprise_services.planning.cluster_address import address_of

logger: logging.Logger = logging.getLogger(name=__name__)


class NameAvailability:
    def __init__(self, *, lookups: NameLookupsByKind, target_resolver: ClusterTargetResolver) -> None:
        self._lookups: NameLookupsByKind = lookups
        self._target_resolver: ClusterTargetResolver = target_resolver

    def taken_names(self, *, clusters: list[ClusterEntry], names: list[RequestedName]) -> list[TakenName]:
        by_kind: dict[NameKind, set[str]] = names_by_kind(names=names)
        return [taken for cluster in clusters for taken in self._taken_on(cluster=cluster, by_kind=by_kind)]

    def ensure_free(self, *, clusters: list[ClusterEntry], names: list[RequestedName]) -> None:
        taken: list[TakenName] = self.taken_names(clusters=clusters, names=names)
        if taken:
            message: str = "; ".join(name.describe() for name in taken)
            logger.warning(msg=message)
            raise NameTakenError(message=message)
        logger.info(msg=f"{len(names)} names are free on {[cluster.name for cluster in clusters]}")

    def _taken_on(self, *, cluster: ClusterEntry, by_kind: dict[NameKind, set[str]]) -> list[TakenName]:
        target: ClusterTarget = self._target_resolver.target_for(address=address_of(cluster=cluster))
        return [
            TakenName(kind=kind, name=name, cluster_name=cluster.name)
            for kind, requested_names in by_kind.items()
            for name in sorted(
                self._lookups.for_kind(kind=kind).existing(target=target, names=requested_names)
            )
        ]


def names_by_kind(*, names: list[RequestedName]) -> dict[NameKind, set[str]]:
    by_kind: dict[NameKind, set[str]] = {}
    for requested_names in names:
        by_kind.setdefault(requested_names.kind, set()).add(requested_names.name)
    return by_kind
