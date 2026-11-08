from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.resource_name_lister import ResourceNameLister


class ListedNameLookup:
    def __init__(self, *, lister: ResourceNameLister) -> None:
        self._lister: ResourceNameLister = lister

    def find_existing(self, *, target: ClusterTarget, names: set[str]) -> set[str]:
        return names & {resource.name for resource in self._lister.list_uids_and_names(target=target)}
