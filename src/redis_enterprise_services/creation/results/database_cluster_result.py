from pydantic import JsonValue

from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.operations.results.database_result import (
    ClusterDatabaseResult,
    DatabaseAccessResult,
    DatabaseClusterResult,
    DatabasePermissionResult,
)
from redis_enterprise_services.resources.models import NamedResource


def database_cluster_result(
    *,
    cluster: ConfiguredCluster,
    database: dict[str, JsonValue],
    endpoints_field: str,
    permissions: list[DatabasePermissionResult],
) -> DatabaseClusterResult:
    return DatabaseClusterResult(
        cluster=cluster.fqdn,
        cluster_url=cluster.api_url,
        network=cluster.network,
        site=cluster.site,
        environment=cluster.environment,
        access=DatabaseAccessResult.model_validate(obj={"endpoints": database[endpoints_field]}),
        db=ClusterDatabaseResult(
            db_uid=NamedResource.model_validate(obj=database).uid,
            settings={name: database[name] for name in NewDatabase.model_fields},
            permissions=permissions,
        ),
    )
