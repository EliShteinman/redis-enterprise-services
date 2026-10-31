from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.repository import ResourceRepository
from redis_enterprise_services.resources.spec import NamedSpec


class RepositoryNameLookup[TSpec: NamedSpec]:
    def __init__(self, *, repository: ResourceRepository[TSpec]) -> None:
        self._repository: ResourceRepository[TSpec] = repository

    def exists(self, *, target: ClusterTarget, name: str) -> bool:
        return bool(self._repository.find_by_name(target=target, name=name))
