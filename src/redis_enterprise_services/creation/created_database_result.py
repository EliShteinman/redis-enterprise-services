from pydantic import JsonValue

from redis_enterprise_services.acls.models import NewAcl
from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.creation.created_resources import created_resource
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.databases.models import DatabaseFieldsSnapshot
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.operations.database_result import DatabasePermissionResult, DatabaseResult
from redis_enterprise_services.planning.creation_step_keys import READ_DATABASE_STEP_KEY
from redis_enterprise_services.planning.database_spec import DatabaseUserSpec
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
from redis_enterprise_services.planning.user_resources import UserResources, user_resources
from redis_enterprise_services.resources.models import CreatedResource, NamedResource
from redis_enterprise_services.saga.contract.saga_record import SagaRecord


def created_database_result(
    *,
    prepared_creation: PreparedCreation,
    record: SagaRecord,
    database_settings: DatabaseSettings,
    resource_naming: UserResourceNaming,
) -> DatabaseResult:
    database: dict[str, JsonValue] = DatabaseFieldsSnapshot.model_validate(
        obj=record.step(key=READ_DATABASE_STEP_KEY).result
    ).values
    cluster: ConfiguredCluster = prepared_creation.cluster
    return DatabaseResult.model_validate(
        obj={
            "name": database["name"],
            "memory_size": database["memory_size"],
            "active_active": False,
            "crdb_guid": None,
            "clusters": [
                {
                    "cluster": cluster.name,
                    "cluster_url": cluster.api_url,
                    "network": cluster.network,
                    "site": cluster.site,
                    "environment": cluster.environment,
                    "access": {"endpoints": database[database_settings.endpoints_field]},
                    "db": {
                        "db_uid": NamedResource.model_validate(obj=database).uid,
                        "settings": {name: database[name] for name in NewDatabase.model_fields},
                        "permissions": [
                            created_permission(
                                record=record,
                                user=user,
                                resources=user_resources(
                                    naming=resource_naming,
                                    database_name=prepared_creation.spec.database.name,
                                    user=user,
                                ),
                            ).model_dump()
                            for user in prepared_creation.spec.users
                        ],
                    },
                }
            ],
        }
    )


def created_permission(
    *, record: SagaRecord, user: DatabaseUserSpec, resources: UserResources
) -> DatabasePermissionResult:
    created_user: CreatedResource = created_resource(record=record, step_key=resources.user.step_key)
    created_acl: CreatedResource = created_resource(record=record, step_key=resources.acl.step_key)
    created_role: CreatedResource = created_resource(record=record, step_key=resources.role.step_key)
    return DatabasePermissionResult(
        user_uid=created_user.uid,
        user_name=created_user.name,
        user_password=user.password,
        acl_uid=created_acl.uid,
        acl_rule=NewAcl.model_validate(obj=created_acl.fields).acl,
        role_uid=created_role.uid,
        role_name=created_role.name,
    )
