from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.crdbs.repository import CrdbRepository
from redis_enterprise_services.planning.availability.name_lookup import NameLookup


class CrdbNameLookup(NameLookup):
    def __init__(self, *, repository: CrdbRepository) -> None:
        self._repository: CrdbRepository = repository

    def find_existing(self, *, target: ClusterTarget, names: set[str]) -> set[str]:
        return names & {crdb.name for crdb in self._repository.list_crdbs(target=target)}
