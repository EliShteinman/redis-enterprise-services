from redis_enterprise_services.composition.cluster_steps import ClusterSteps
from redis_enterprise_services.composition.crdb_steps import CrdbSteps
from redis_enterprise_services.config.role_management import RoleManagement
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.planning.active_active_creation_planner import ActiveActiveCreationPlanner
from redis_enterprise_services.planning.database_defaults import DatabaseDefaults
from redis_enterprise_services.planning.single_site_creation_planner import SingleSiteCreationPlanner
from redis_enterprise_services.planning.step_factories.crdb_permission_step_factory import (
    CrdbPermissionStepFactory,
)
from redis_enterprise_services.planning.step_factories.crdb_step_factory import CrdbStepFactory
from redis_enterprise_services.planning.step_factories.database_permission_step_factory import (
    DatabasePermissionStepFactory,
)
from redis_enterprise_services.planning.step_factories.database_step_factory import DatabaseStepFactory
from redis_enterprise_services.planning.step_factories.read_crdb_step_factory import ReadCrdbStepFactory
from redis_enterprise_services.planning.step_factories.read_database_step_factory import (
    ReadDatabaseStepFactory,
)
from redis_enterprise_services.planning.step_factories.role_permission_values import RolePermissionValues
from redis_enterprise_services.planning.step_factories.user_resource_step_factory import (
    UserResourceStepFactory,
)
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
from redis_enterprise_services.resources.creation_body_builder import CreationBodyBuilder


def build_single_site_planner(
    *,
    role_management: RoleManagement,
    permission_values: RolePermissionValues,
    resource_naming: UserResourceNaming,
    steps: ClusterSteps,
) -> SingleSiteCreationPlanner:
    return SingleSiteCreationPlanner(
        resource_naming=resource_naming,
        database_steps=DatabaseStepFactory(create_database_step=steps.create_database),
        user_resource_steps=build_user_resource_step_factory(role_management=role_management, steps=steps),
        permission_steps=DatabasePermissionStepFactory(
            update_database_step=steps.update_database, permission_values=permission_values
        ),
        read_database_steps=ReadDatabaseStepFactory(
            read_database_step=steps.read_database, permission_values=permission_values
        ),
    )


def build_active_active_planner(
    *,
    role_management: RoleManagement,
    permission_values: RolePermissionValues,
    resource_naming: UserResourceNaming,
    database_defaults: DatabaseDefaults,
    database_body_builder: CreationBodyBuilder[NewDatabase],
    secret_fields: frozenset[str],
    steps: ClusterSteps,
    crdb_steps: CrdbSteps,
) -> ActiveActiveCreationPlanner:
    return ActiveActiveCreationPlanner(
        resource_naming=resource_naming,
        database_defaults=database_defaults,
        crdb_steps=CrdbStepFactory(
            create_crdb_step=crdb_steps.create_crdb,
            find_local_instance_step=crdb_steps.find_local_crdb_instance,
        ),
        user_resource_steps=build_user_resource_step_factory(role_management=role_management, steps=steps),
        permission_steps=CrdbPermissionStepFactory(
            update_instances_step=crdb_steps.update_crdb_instances, permission_values=permission_values
        ),
        read_database_steps=ReadDatabaseStepFactory(
            read_database_step=steps.read_database, permission_values=permission_values
        ),
        read_crdb_steps=ReadCrdbStepFactory(
            read_crdb_step=crdb_steps.read_crdb,
            database_body_builder=database_body_builder,
            secret_fields=secret_fields,
        ),
    )


def build_user_resource_step_factory(
    *, role_management: RoleManagement, steps: ClusterSteps
) -> UserResourceStepFactory:
    return UserResourceStepFactory(
        role_management=role_management,
        create_acl_step=steps.create_acl,
        create_role_step=steps.create_role,
        create_user_step=steps.create_user,
    )
