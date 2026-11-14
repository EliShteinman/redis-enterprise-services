from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.planning.database_spec import DatabaseUserSpec
from redis_enterprise_services.planning.lock_keys import database_lock_key, user_lock_key
from redis_enterprise_services.planning.role_permission import RolePermission
from redis_enterprise_services.planning.user_resources import UserResources
from redis_enterprise_services.resources.models import CreatedResource, CreateResourceInput
from redis_enterprise_services.resources.named_spec import NamedSpec
from redis_enterprise_services.saga.plan.step_results import StepResults
from redis_enterprise_services.users.models import NewUser


def fixed_resource_input[TSpec: NamedSpec](
    *, step_results: StepResults, address: ClusterAddress, spec: TSpec
) -> CreateResourceInput[TSpec]:
    return CreateResourceInput(cluster=address, spec=spec)


def user_input(
    *, step_results: StepResults, address: ClusterAddress, user: DatabaseUserSpec, role_step_key: str
) -> CreateResourceInput[NewUser]:
    return CreateResourceInput(
        cluster=address,
        spec=NewUser(
            name=user.name,
            password=user.password,
            role_uids=[uid_created_by_step(step_results=step_results, step_key=role_step_key)],
        ),
    )


def creation_lock_keys(*, cluster_url: str, database_name: str, user_names: list[str]) -> list[str]:
    return [
        database_lock_key(cluster_url=cluster_url, database_name=database_name),
        *(user_lock_key(cluster_url=cluster_url, user_name=user_name) for user_name in user_names),
    ]


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


def uid_created_by_step(*, step_results: StepResults, step_key: str) -> int:
    return step_results.result_of(key=step_key, result_type=CreatedResource).uid
