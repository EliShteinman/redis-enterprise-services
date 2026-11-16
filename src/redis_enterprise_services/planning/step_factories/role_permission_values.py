from pydantic import JsonValue

from redis_enterprise_services.planning.role_permission import RolePermission
from redis_enterprise_services.planning.step_factories.step_inputs import uid_created_by_step
from redis_enterprise_services.planning.user_resources import UserResources
from redis_enterprise_services.saga.plan.step_results import StepResults


class RolePermissionValues:
    def __init__(self, *, roles_permissions_field: str) -> None:
        self._roles_permissions_field: str = roles_permissions_field

    def of_users(
        self, *, step_results: StepResults, resources_of_users: list[UserResources]
    ) -> dict[str, JsonValue]:
        return {
            self._roles_permissions_field: [
                permission.model_dump(mode="json")
                for permission in role_permissions(
                    step_results=step_results, resources_of_users=resources_of_users
                )
            ]
        }


def role_permissions(
    *, step_results: StepResults, resources_of_users: list[UserResources]
) -> list[RolePermission]:
    return [
        RolePermission(
            role_uid=uid_created_by_step(step_results=step_results, step_key=resources.role.step_key),
            redis_acl_uid=uid_created_by_step(step_results=step_results, step_key=resources.acl.step_key),
        )
        for resources in resources_of_users
    ]
