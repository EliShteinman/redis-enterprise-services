from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.planning.availability.name_lookup import NameLookup


class CombinedNameLookup(NameLookup):
    def __init__(self, *, lookups: list[NameLookup]) -> None:
        self._lookups: list[NameLookup] = lookups

    def find_existing(self, *, target: ClusterTarget, names: set[str]) -> set[str]:
        return {name for lookup in self._lookups for name in lookup.find_existing(target=target, names=names)}
