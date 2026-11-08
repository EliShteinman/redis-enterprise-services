from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.named_resource_lister import NamedResourceLister


class ListedNameLookup:
    def __init__(self, *, lister: NamedResourceLister) -> None:
        self._lister: NamedResourceLister = lister

    def existing(self, *, target: ClusterTarget, names: set[str]) -> set[str]:
        return names & {resource.name for resource in self._lister.list_named(target=target)}
