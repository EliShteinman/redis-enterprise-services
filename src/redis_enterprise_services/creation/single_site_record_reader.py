from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.redis_api.cluster_api_settings import ClusterFieldSettings
from redis_enterprise_services.config.redis_api.database_settings import DatabaseSettings
from redis_enterprise_services.creation.creation_record_reader import CreationRecordReader
from redis_enterprise_services.creation.preparation.prepared_creation import PreparedCreation
from redis_enterprise_services.creation.results.created_database_result import created_database_result
from redis_enterprise_services.operations.results.database_result import DatabaseResult
from redis_enterprise_services.planning.planned.planned_resources import planned_resources_by_step_key
from redis_enterprise_services.planning.planned.site_planned_resource import SitePlannedResource
from redis_enterprise_services.planning.planned.user_resource_naming import UserResourceNaming
from redis_enterprise_services.saga.contract.saga_record import SagaRecord


class SingleSiteRecordReader(CreationRecordReader[PreparedCreation]):
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

    def database_result(self, *, prepared_creation: PreparedCreation, record: SagaRecord) -> DatabaseResult:
        return created_database_result(
            prepared_creation=prepared_creation,
            record=record,
            database_settings=self._database_settings,
            cluster_fields=self._cluster_fields,
            resource_naming=self._resource_naming,
        )

    def planned_resources(self, *, prepared_creation: PreparedCreation) -> dict[str, SitePlannedResource]:
        return {
            step_key: SitePlannedResource(cluster=prepared_creation.cluster, resource=planned)
            for step_key, planned in planned_resources_by_step_key(
                spec=prepared_creation.spec, resource_naming=self._resource_naming
            ).items()
        }

    def cluster_of_step(self, *, prepared_creation: PreparedCreation, step_key: str) -> ConfiguredCluster:
        return prepared_creation.cluster
