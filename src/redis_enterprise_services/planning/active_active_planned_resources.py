from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.planning.crdb_coordinator import coordinator_of
from redis_enterprise_services.planning.creation_step_keys import CRDB_STEP_KEY, PERMISSIONS_STEP_KEY, on_site
from redis_enterprise_services.planning.database_spec import DatabaseSpec, DatabaseUserSpec
from redis_enterprise_services.planning.planned_resources import (
    CRDB_RESOURCE_TYPE,
    PERMISSIONS_RESOURCE_TYPE,
    PlannedResource,
)
from redis_enterprise_services.planning.site_planned_resource import SitePlannedResource
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
from redis_enterprise_services.planning.user_resources import UserResource, UserResources, user_resources


def active_active_planned_resources(
    *, spec: DatabaseSpec, resource_naming: UserResourceNaming, clusters: list[ConfiguredCluster]
) -> dict[str, SitePlannedResource]:
    database_name: str = spec.database.name
    coordinator: ConfiguredCluster = coordinator_of(clusters=clusters)
    planned: dict[str, SitePlannedResource] = {
        CRDB_STEP_KEY: SitePlannedResource(
            cluster=coordinator,
            resource=PlannedResource(
                resource_type=CRDB_RESOURCE_TYPE, name=database_name, uid_step_key=CRDB_STEP_KEY
            ),
        )
    }
    for cluster in clusters:
        for user in spec.users:
            for resource in site_user_resources(
                naming=resource_naming, database_name=database_name, user=user, cluster_fqdn=cluster.fqdn
            ).in_creation_order():
                planned[resource.step_key] = SitePlannedResource(
                    cluster=cluster,
                    resource=PlannedResource(
                        resource_type=resource.kind, name=resource.name, uid_step_key=resource.step_key
                    ),
                )
    if spec.users:
        planned[PERMISSIONS_STEP_KEY] = SitePlannedResource(
            cluster=coordinator,
            resource=PlannedResource(
                resource_type=PERMISSIONS_RESOURCE_TYPE, name=database_name, uid_step_key=CRDB_STEP_KEY
            ),
        )
    return planned


def site_user_resources(
    *, naming: UserResourceNaming, database_name: str, user: DatabaseUserSpec, cluster_fqdn: str
) -> UserResources:
    resources: UserResources = user_resources(naming=naming, database_name=database_name, user=user)
    return UserResources(
        acl=on_site_resource(cluster_fqdn=cluster_fqdn, resource=resources.acl),
        role=on_site_resource(cluster_fqdn=cluster_fqdn, resource=resources.role),
        user=on_site_resource(cluster_fqdn=cluster_fqdn, resource=resources.user),
    )


def on_site_resource(*, cluster_fqdn: str, resource: UserResource) -> UserResource:
    site_step_key: str = on_site(cluster_fqdn=cluster_fqdn, step_key=resource.step_key)
    return resource.model_copy(update={"step_key": site_step_key})
