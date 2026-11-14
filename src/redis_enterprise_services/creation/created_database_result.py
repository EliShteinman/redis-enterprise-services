from pydantic import BaseModel, JsonValue

from redis_enterprise_services.acls.models import NewAcl
from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.creation.created_resources import created_resource
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.databases.models import DatabaseFieldsSnapshot
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.operations.database_result import DatabasePermissionResult, DatabaseResult
from redis_enterprise_services.planning.active_active_planned_resources import site_user_resources
from redis_enterprise_services.planning.creation_step_keys import (
    CRDB_STEP_KEY,
    READ_DATABASE_STEP_KEY,
    on_site,
)
from redis_enterprise_services.planning.database_spec import DatabaseUserSpec
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
from redis_enterprise_services.planning.user_resources import UserResources, user_resources
from redis_enterprise_services.resources.models import CreatedResource, NamedResource
from redis_enterprise_services.saga.contract.saga_record import SagaRecord
from redis_enterprise_services.steps.create_crdb import CreatedCrdb


def created_database_result(
    *,
    prepared_creation: PreparedCreation,
    record: SagaRecord,
    database_settings: DatabaseSettings,
    resource_naming: UserResourceNaming,
) -> DatabaseResult:
    sites: list[CreatedSite] = created_sites(
        prepared_creation=prepared_creation, resource_naming=resource_naming
    )
    first_site: dict[str, JsonValue] = read_database_values(record=record, step_key=sites[0].read_step_key)
    return DatabaseResult.model_validate(
        obj={
            "name": first_site["name"],
            "memory_size": first_site["memory_size"],
            "active_active": prepared_creation.active_active,
            "crdb_guid": created_crdb_guid(prepared_creation=prepared_creation, record=record),
            "clusters": [
                cluster_result(
                    site=site,
                    database=read_database_values(record=record, step_key=site.read_step_key),
                    permissions=[
                        created_permission(record=record, user=user, resources=resources).model_dump()
                        for user, resources in site.users
                    ],
                    database_settings=database_settings,
                )
                for site in sites
            ],
        }
    )


class CreatedSite(BaseModel):
    cluster: ConfiguredCluster
    read_step_key: str
    users: list[tuple[DatabaseUserSpec, UserResources]]


def created_sites(
    *, prepared_creation: PreparedCreation, resource_naming: UserResourceNaming
) -> list[CreatedSite]:
    database_name: str = prepared_creation.spec.database.name
    if not prepared_creation.active_active:
        return [
            CreatedSite(
                cluster=prepared_creation.cluster,
                read_step_key=READ_DATABASE_STEP_KEY,
                users=[
                    (user, user_resources(naming=resource_naming, database_name=database_name, user=user))
                    for user in prepared_creation.spec.users
                ],
            )
        ]
    return [
        CreatedSite(
            cluster=cluster,
            read_step_key=on_site(cluster_name=cluster.name, step_key=READ_DATABASE_STEP_KEY),
            users=[
                (
                    user,
                    site_user_resources(
                        naming=resource_naming,
                        database_name=database_name,
                        user=user,
                        cluster_name=cluster.name,
                    ),
                )
                for user in prepared_creation.spec.users
            ],
        )
        for cluster in prepared_creation.clusters
    ]


def created_crdb_guid(*, prepared_creation: PreparedCreation, record: SagaRecord) -> str | None:
    if not prepared_creation.active_active:
        return None
    return CreatedCrdb.model_validate(obj=record.step(key=CRDB_STEP_KEY).result).guid


def read_database_values(*, record: SagaRecord, step_key: str) -> dict[str, JsonValue]:
    return DatabaseFieldsSnapshot.model_validate(obj=record.step(key=step_key).result).values


def cluster_result(
    *,
    site: CreatedSite,
    database: dict[str, JsonValue],
    permissions: list[JsonValue],
    database_settings: DatabaseSettings,
) -> JsonValue:
    cluster: ConfiguredCluster = site.cluster
    return {
        "cluster": cluster.name,
        "cluster_url": cluster.api_url,
        "network": cluster.network,
        "site": cluster.site,
        "environment": cluster.environment,
        "access": {"endpoints": database[database_settings.endpoints_field]},
        "db": {
            "db_uid": NamedResource.model_validate(obj=database).uid,
            "settings": {name: database[name] for name in NewDatabase.model_fields},
            "permissions": permissions,
        },
    }


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
