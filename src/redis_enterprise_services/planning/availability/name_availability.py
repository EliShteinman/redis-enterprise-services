import logging

from redis_enterprise_services.cluster.cluster_target_resolver import ClusterTargetResolver
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
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

    def find_taken_names(
        self, *, clusters: list[ConfiguredCluster], requested_names: list[RequestedName]
    ) -> list[TakenName]:
        by_kind: dict[NameKind, set[str]] = names_by_kind(requested_names=requested_names)
        return [
            taken
            for cluster in clusters
            for taken in self._find_taken_on_cluster(cluster=cluster, by_kind=by_kind)
        ]

    def find_taken_and_raise_if_any(
        self, *, clusters: list[ConfiguredCluster], requested_names: list[RequestedName]
    ) -> None:
        taken: list[TakenName] = self.find_taken_names(clusters=clusters, requested_names=requested_names)
        if taken:
            message: str = "; ".join(taken_name.describe() for taken_name in taken)
            logger.warning(msg=message)
            raise NameTakenError(message=message)
        logger.info(msg=f"{len(requested_names)} names are free on {[cluster.name for cluster in clusters]}")

    def _find_taken_on_cluster(
        self, *, cluster: ConfiguredCluster, by_kind: dict[NameKind, set[str]]
    ) -> list[TakenName]:
        target: ClusterTarget = self._target_resolver.target_for(address=address_of(cluster=cluster))
        return [
            TakenName(kind=kind, name=name, cluster_name=cluster.name)
            for kind, names_of_kind in by_kind.items()
            for name in sorted(
                self._lookups.for_kind(kind=kind).find_existing(target=target, names=names_of_kind)
            )
        ]


def names_by_kind(*, requested_names: list[RequestedName]) -> dict[NameKind, set[str]]:
    by_kind: dict[NameKind, set[str]] = {}
    for requested in requested_names:
        by_kind.setdefault(requested.kind, set()).add(requested.name)
    return by_kind
