from pydantic import JsonValue

from redis_enterprise_services.config.redis_api.cluster_api_settings import ClusterFieldSettings
from redis_enterprise_services.config.redis_api.database_settings import DatabaseSettings
from redis_enterprise_services.creation.preparation.prepared_creation import PreparedCreation
from redis_enterprise_services.creation.results.created_permission import created_permission
from redis_enterprise_services.creation.results.database_cluster_result import database_cluster_result
from redis_enterprise_services.databases.models import DatabaseFieldsSnapshot
from redis_enterprise_services.operations.results.database_result import DatabaseResult
from redis_enterprise_services.planning.keys.creation_step_keys import READ_DATABASE_STEP_KEY
from redis_enterprise_services.planning.planned.user_resource_naming import UserResourceNaming
from redis_enterprise_services.planning.planned.user_resources import user_resources
from redis_enterprise_services.saga.contract.saga_record import SagaRecord


def created_database_result(
    *,
    prepared_creation: PreparedCreation,
    record: SagaRecord,
    database_settings: DatabaseSettings,
    cluster_fields: ClusterFieldSettings,
    resource_naming: UserResourceNaming,
) -> DatabaseResult:
    database: dict[str, JsonValue] = DatabaseFieldsSnapshot.model_validate(
        obj=record.step(key=READ_DATABASE_STEP_KEY).result
    ).values
    return DatabaseResult.model_validate(
        obj={
            "kind": "single_site",
            "name": database[cluster_fields.name],
            "memory_size": database[cluster_fields.memory_size],
            "cluster": database_cluster_result(
                cluster=prepared_creation.cluster,
                database=database,
                endpoints_field=database_settings.endpoints_field,
                permissions=[
                    created_permission(
                        record=record,
                        user=user,
                        resources=user_resources(
                            naming=resource_naming,
                            database_name=prepared_creation.spec.database.name,
                            user=user,
                        ),
                    )
                    for user in prepared_creation.spec.users
                ],
            ),
        }
    )
