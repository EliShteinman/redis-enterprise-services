from pydantic import JsonValue

from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.redis_api.cluster_api_settings import ClusterFieldSettings
from redis_enterprise_services.config.redis_api.database_settings import DatabaseSettings
from redis_enterprise_services.creation.preparation.prepared_active_active_creation import (
    PreparedActiveActiveCreation,
)
from redis_enterprise_services.creation.results.crdb_instance_of_cluster import crdb_instance_of_cluster
from redis_enterprise_services.creation.results.created_crdb_guid import created_crdb_guid
from redis_enterprise_services.creation.results.created_permission import created_permission
from redis_enterprise_services.databases.models import DatabaseFieldsSnapshot
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.operations.results.active_active_database_result import (
    ActiveActiveDatabaseResult,
)
from redis_enterprise_services.planning.keys.creation_step_keys import (
    READ_CRDB_STEP_KEY,
    READ_DATABASE_STEP_KEY,
    on_site,
)
from redis_enterprise_services.planning.planned.active_active_planned_resources import site_user_resources
from redis_enterprise_services.planning.planned.user_resource_naming import UserResourceNaming
from redis_enterprise_services.planning.spec.active_active_spec import ActiveActiveSpec
from redis_enterprise_services.resources.models import NamedResource
from redis_enterprise_services.saga.contract.saga_record import SagaRecord
from redis_enterprise_services.steps.crdb.read_crdb import CrdbConfigSnapshot, CrdbInstanceSettings


def created_active_active_result(
    *,
    prepared_creation: PreparedActiveActiveCreation,
    record: SagaRecord,
    database_settings: DatabaseSettings,
    cluster_fields: ClusterFieldSettings,
    resource_naming: UserResourceNaming,
) -> ActiveActiveDatabaseResult:
    crdb: CrdbConfigSnapshot = CrdbConfigSnapshot.model_validate(
        obj=record.step(key=READ_CRDB_STEP_KEY).result
    )
    databases: list[dict[str, JsonValue]] = [
        database_read_on(cluster=cluster, record=record) for cluster in prepared_creation.clusters
    ]
    return ActiveActiveDatabaseResult.model_validate(
        obj={
            "kind": "active_active",
            "name": databases[0][cluster_fields.name],
            "memory_size": databases[0][cluster_fields.memory_size],
            "crdb": {
                "guid": created_crdb_guid(record=record),
                "causal_consistency": crdb.causal_consistency,
                "encryption": crdb.encryption,
                "featureset_version": crdb.featureset_version,
                "protocol_version": crdb.protocol_version,
                "default_db_config": crdb.default_db_config,
            },
            "clusters": [
                cluster_result(
                    cluster=cluster,
                    instance=crdb_instance_of_cluster(cluster=cluster, instances=crdb.instances),
                    database=database,
                    endpoints_field=database_settings.endpoints_field,
                    permissions=permissions_on(
                        cluster=cluster,
                        spec=prepared_creation.spec,
                        record=record,
                        resource_naming=resource_naming,
                    ),
                )
                for cluster, database in zip(prepared_creation.clusters, databases, strict=True)
            ],
        }
    )


def database_read_on(*, cluster: ConfiguredCluster, record: SagaRecord) -> dict[str, JsonValue]:
    read_step_key: str = on_site(cluster_fqdn=cluster.fqdn, step_key=READ_DATABASE_STEP_KEY)
    return DatabaseFieldsSnapshot.model_validate(obj=record.step(key=read_step_key).result).values


def permissions_on(
    *,
    cluster: ConfiguredCluster,
    spec: ActiveActiveSpec,
    record: SagaRecord,
    resource_naming: UserResourceNaming,
) -> list[JsonValue]:
    return [
        created_permission(
            record=record,
            user=user,
            resources=site_user_resources(
                naming=resource_naming,
                database_name=spec.database.name,
                user=user,
                cluster_fqdn=cluster.fqdn,
            ),
        ).model_dump()
        for user in spec.users
    ]


def cluster_result(
    *,
    cluster: ConfiguredCluster,
    instance: CrdbInstanceSettings,
    database: dict[str, JsonValue],
    endpoints_field: str,
    permissions: list[JsonValue],
) -> JsonValue:
    return {
        "cluster": cluster.fqdn,
        "cluster_url": cluster.api_url,
        "network": cluster.network,
        "site": cluster.site,
        "environment": cluster.environment,
        "instance_id": instance.id,
        "compression": instance.compression,
        "access": {"endpoints": database[endpoints_field]},
        "db": {
            "db_uid": NamedResource.model_validate(obj=database).uid,
            "settings": {name: database[name] for name in NewDatabase.model_fields},
            "permissions": permissions,
        },
    }
