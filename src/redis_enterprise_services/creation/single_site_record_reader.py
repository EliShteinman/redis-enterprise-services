from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.creation.created_database_result import created_database_result
from redis_enterprise_services.creation.creation_record_reader import CreationRecordReader
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.operations.database_result import DatabaseResult
from redis_enterprise_services.planning.active_active_planned_resources import SitePlannedResource
from redis_enterprise_services.planning.planned_resources import planned_resources_by_step_key
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
from redis_enterprise_services.saga.contract.saga_record import SagaRecord


class SingleSiteRecordReader(CreationRecordReader[PreparedCreation]):
    def __init__(self, *, resource_naming: UserResourceNaming, database_settings: DatabaseSettings) -> None:
        self._resource_naming: UserResourceNaming = resource_naming
        self._database_settings: DatabaseSettings = database_settings

    def database_result(self, *, prepared_creation: PreparedCreation, record: SagaRecord) -> DatabaseResult:
        return created_database_result(
            prepared_creation=prepared_creation,
            record=record,
            database_settings=self._database_settings,
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
