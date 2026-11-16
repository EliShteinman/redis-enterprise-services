from typing import Protocol

from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.operations.results.active_active_database_result import (
    ActiveActiveDatabaseResult,
)
from redis_enterprise_services.operations.results.database_result import DatabaseResult
from redis_enterprise_services.planning.planned.site_planned_resource import SitePlannedResource
from redis_enterprise_services.saga.contract.saga_record import SagaRecord


class CreationRecordReader[TPrepared](Protocol):
    def database_result(
        self, *, prepared_creation: TPrepared, record: SagaRecord
    ) -> DatabaseResult | ActiveActiveDatabaseResult: ...

    def planned_resources(self, *, prepared_creation: TPrepared) -> dict[str, SitePlannedResource]: ...

    def cluster_of_step(self, *, prepared_creation: TPrepared, step_key: str) -> ConfiguredCluster: ...
