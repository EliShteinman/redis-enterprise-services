from functools import partial

from redis_enterprise_services.acls.models import NewAcl
from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.config.defaults.role_management import RoleManagement
from redis_enterprise_services.planning.planned.user_resources import UserResource, UserResources
from redis_enterprise_services.planning.spec.database_spec import DatabaseUserSpec
from redis_enterprise_services.planning.step_factories.step_inputs import (
    UidFromStepResults,
    fixed_input,
    uid_created_by_step,
)
from redis_enterprise_services.resources.models import CreatedResource, CreateResourceInput
from redis_enterprise_services.roles.models import NewRole
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.plan.planned_step import PlannedStep
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep
from redis_enterprise_services.saga.plan.step_results import StepResults
from redis_enterprise_services.users.models import NewUser


class UserResourceStepFactory:
    def __init__(
        self,
        *,
        role_management: RoleManagement,
        create_acl_step: SagaStep[CreateResourceInput[NewAcl], CreatedResource],
        create_role_step: SagaStep[CreateResourceInput[NewRole], CreatedResource],
        create_user_step: SagaStep[CreateResourceInput[NewUser], CreatedResource],
    ) -> None:
        self._role_management: RoleManagement = role_management
        self._create_acl_step: SagaStep[CreateResourceInput[NewAcl], CreatedResource] = create_acl_step
        self._create_role_step: SagaStep[CreateResourceInput[NewRole], CreatedResource] = create_role_step
        self._create_user_step: SagaStep[CreateResourceInput[NewUser], CreatedResource] = create_user_step

    def steps_for_user(
        self,
        *,
        address: ClusterAddress,
        user: DatabaseUserSpec,
        resources: UserResources,
        database_uid: UidFromStepResults,
    ) -> list[PreparableStep]:
        return [
            self._acl_step(address=address, user=user, acl=resources.acl),
            self._role_step(address=address, role=resources.role, database_uid=database_uid),
            self._user_step(address=address, user=user, resources=resources),
        ]

    def _acl_step(
        self, *, address: ClusterAddress, user: DatabaseUserSpec, acl: UserResource
    ) -> PreparableStep:
        return PlannedStep(
            key=acl.step_key,
            step=self._create_acl_step,
            build_input=partial(
                fixed_input,
                step_input=CreateResourceInput(
                    cluster=address, spec=NewAcl(name=acl.name, acl=user.acl_rule)
                ),
            ),
        )

    def _role_step(
        self, *, address: ClusterAddress, role: UserResource, database_uid: UidFromStepResults
    ) -> PreparableStep:
        return PlannedStep(
            key=role.step_key,
            step=self._create_role_step,
            build_input=partial(
                self._role_input, address=address, role_name=role.name, database_uid=database_uid
            ),
        )

    def _role_input(
        self,
        *,
        step_results: StepResults,
        address: ClusterAddress,
        role_name: str,
        database_uid: UidFromStepResults,
    ) -> CreateResourceInput[NewRole]:
        return CreateResourceInput(
            cluster=address,
            spec=NewRole(
                name=role_name,
                management=self._role_management,
                database_uids=[database_uid(step_results=step_results)],
            ),
        )

    def _user_step(
        self, *, address: ClusterAddress, user: DatabaseUserSpec, resources: UserResources
    ) -> PreparableStep:
        return PlannedStep(
            key=resources.user.step_key,
            step=self._create_user_step,
            build_input=partial(
                user_input, address=address, user=user, role_step_key=resources.role.step_key
            ),
        )


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
