from redis_enterprise_services.composition.cluster_steps import ClusterSteps
from redis_enterprise_services.config.defaults.role_management import RoleManagement
from redis_enterprise_services.planning.planned.user_resource_naming import UserResourceNaming
from redis_enterprise_services.planning.single_site_creation_planner import SingleSiteCreationPlanner
from redis_enterprise_services.planning.step_factories.database_permission_step_factory import (
    DatabasePermissionStepFactory,
)
from redis_enterprise_services.planning.step_factories.database_step_factory import DatabaseStepFactory
from redis_enterprise_services.planning.step_factories.read_database_step_factory import (
    ReadDatabaseStepFactory,
)
from redis_enterprise_services.planning.step_factories.role_permission_values import RolePermissionValues
from redis_enterprise_services.planning.step_factories.user_resource_step_factory import (
    UserResourceStepFactory,
)


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


def build_user_resource_step_factory(
    *, role_management: RoleManagement, steps: ClusterSteps
) -> UserResourceStepFactory:
    return UserResourceStepFactory(
        role_management=role_management,
        create_acl_step=steps.create_acl,
        create_role_step=steps.create_role,
        create_user_step=steps.create_user,
    )
