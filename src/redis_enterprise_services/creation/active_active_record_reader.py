from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.redis_api.cluster_api_settings import ClusterFieldSettings
from redis_enterprise_services.config.redis_api.database_settings import DatabaseSettings
from redis_enterprise_services.creation.created_active_active_result import created_active_active_result
from redis_enterprise_services.creation.creation_record_reader import CreationRecordReader
from redis_enterprise_services.creation.prepared_active_active_creation import PreparedActiveActiveCreation
from redis_enterprise_services.operations.results.active_active_database_result import (
    ActiveActiveDatabaseResult,
)
from redis_enterprise_services.planning.keys.creation_step_keys import (
    LOCAL_DATABASE_STEP_KEY,
    READ_DATABASE_STEP_KEY,
    on_site,
)
from redis_enterprise_services.planning.placement.crdb_coordinator import coordinator_of
from redis_enterprise_services.planning.planned.active_active_planned_resources import (
    active_active_planned_resources,
)
from redis_enterprise_services.planning.planned.site_planned_resource import SitePlannedResource
from redis_enterprise_services.planning.planned.user_resource_naming import UserResourceNaming
from redis_enterprise_services.saga.contract.saga_record import SagaRecord

DATABASE_STEP_KEYS_ON_A_SITE: tuple[str, ...] = (LOCAL_DATABASE_STEP_KEY, READ_DATABASE_STEP_KEY)


class ActiveActiveRecordReader(CreationRecordReader[PreparedActiveActiveCreation]):
    def __init__(
        self,
        *,
        resource_naming: UserResourceNaming,
        database_settings: DatabaseSettings,
        cluster_fields: ClusterFieldSettings,
    ) -> None:
        self._resource_naming: UserResourceNaming = resource_naming
        self._database_settings: DatabaseSettings = database_settings
        self._cluster_fields: ClusterFieldSettings = cluster_fields

    def database_result(
        self, *, prepared_creation: PreparedActiveActiveCreation, record: SagaRecord
    ) -> ActiveActiveDatabaseResult:
        return created_active_active_result(
            prepared_creation=prepared_creation,
            record=record,
            database_settings=self._database_settings,
            cluster_fields=self._cluster_fields,
            resource_naming=self._resource_naming,
        )

    def planned_resources(
        self, *, prepared_creation: PreparedActiveActiveCreation
    ) -> dict[str, SitePlannedResource]:
        return active_active_planned_resources(
            spec=prepared_creation.spec,
            resource_naming=self._resource_naming,
            clusters=prepared_creation.clusters,
        )

    def cluster_of_step(
        self, *, prepared_creation: PreparedActiveActiveCreation, step_key: str
    ) -> ConfiguredCluster:
        planned: SitePlannedResource | None = self.planned_resources(prepared_creation=prepared_creation).get(
            step_key
        )
        if planned is not None:
            return planned.cluster
        return next(
            (
                cluster
                for cluster in prepared_creation.clusters
                if step_key in database_step_keys_on(cluster=cluster)
            ),
            coordinator_of(clusters=prepared_creation.clusters),
        )


def database_step_keys_on(*, cluster: ConfiguredCluster) -> set[str]:
    return {on_site(cluster_fqdn=cluster.fqdn, step_key=key) for key in DATABASE_STEP_KEYS_ON_A_SITE}
