from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.planning.availability.creation_naming import CreationNaming
from redis_enterprise_services.planning.availability.name_availability import NameAvailability
from redis_enterprise_services.planning.availability.name_check_scope import NameCheckScope
from redis_enterprise_services.planning.database_spec import DatabaseSpec


class CreationNamesCheck:
    def __init__(
        self,
        *,
        name_check_scope: NameCheckScope,
        name_availability: NameAvailability,
        creation_naming: CreationNaming,
    ) -> None:
        self._name_check_scope: NameCheckScope = name_check_scope
        self._name_availability: NameAvailability = name_availability
        self._creation_naming: CreationNaming = creation_naming

    def ensure_free(self, *, cluster: ConfiguredCluster, spec: DatabaseSpec) -> None:
        self._name_availability.ensure_free(
            clusters=self._name_check_scope.clusters_to_check(chosen=cluster),
            requested_names=self._creation_naming.requested_names(spec=spec),
        )
