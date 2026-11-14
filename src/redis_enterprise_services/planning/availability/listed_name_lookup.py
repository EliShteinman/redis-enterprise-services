from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.planning.availability.name_lookup import NameLookup
from redis_enterprise_services.resources.resource_name_lister import ResourceNameLister


class ListedNameLookup(NameLookup):
    def __init__(self, *, lister: ResourceNameLister) -> None:
        self._lister: ResourceNameLister = lister

    def find_existing(self, *, target: ClusterTarget, names: set[str]) -> set[str]:
        return names & {resource.name for resource in self._lister.list_objects(target=target)}
