import logging
from functools import partial

from pydantic import JsonValue

from redis_enterprise_services.acls.models import NewAcl
from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.config.cluster_api_settings import ClusterFieldSettings
from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.role_management import RoleManagement
from redis_enterprise_services.databases.models import DatabaseFieldsSnapshot
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.planning.cluster_address import address_of
from redis_enterprise_services.planning.creation_step_keys import (
    DATABASE_STEP_KEY,
    PERMISSIONS_STEP_KEY,
    READ_DATABASE_STEP_KEY,
    acl_step_key,
    role_step_key,
    user_step_key,
)
from redis_enterprise_services.planning.database_spec import DatabaseSpec, DatabaseUserSpec
from redis_enterprise_services.planning.role_permission import RolePermission
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
from redis_enterprise_services.resources.models import CreatedResource, CreateResourceInput
from redis_enterprise_services.resources.named_spec import NamedSpec
from redis_enterprise_services.roles.models import NewRole
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.plan.planned_step import PlannedStep
from redis_enterprise_services.saga.plan.saga_plan import SagaPlan
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep
from redis_enterprise_services.saga.plan.step_results import StepResults
from redis_enterprise_services.steps.read_database import ReadDatabaseInput
from redis_enterprise_services.steps.update_database import UpdateDatabaseInput
from redis_enterprise_services.users.models import NewUser

logger: logging.Logger = logging.getLogger(name=__name__)

DATABASE_LOCK_SEGMENT: str = "database"
USER_LOCK_SEGMENT: str = "user"


class SingleSiteCreationPlanner:
    def __init__(
        self,
        *,
        role_management: RoleManagement,
        cluster_fields: ClusterFieldSettings,
        resource_naming: UserResourceNaming,
        create_database_step: SagaStep[CreateResourceInput[NewDatabase], CreatedResource],
        create_acl_step: SagaStep[CreateResourceInput[NewAcl], CreatedResource],
        create_role_step: SagaStep[CreateResourceInput[NewRole], CreatedResource],
        create_user_step: SagaStep[CreateResourceInput[NewUser], CreatedResource],
        update_database_step: SagaStep[UpdateDatabaseInput, DatabaseFieldsSnapshot],
        read_database_step: SagaStep[ReadDatabaseInput, DatabaseFieldsSnapshot],
    ) -> None:
        self._role_management: RoleManagement = role_management
        self._cluster_fields: ClusterFieldSettings = cluster_fields
        self._resource_naming: UserResourceNaming = resource_naming
        self._create_database_step: SagaStep[CreateResourceInput[NewDatabase], CreatedResource] = (
            create_database_step
        )
        self._create_acl_step: SagaStep[CreateResourceInput[NewAcl], CreatedResource] = create_acl_step
        self._create_role_step: SagaStep[CreateResourceInput[NewRole], CreatedResource] = create_role_step
        self._create_user_step: SagaStep[CreateResourceInput[NewUser], CreatedResource] = create_user_step
        self._update_database_step: SagaStep[UpdateDatabaseInput, DatabaseFieldsSnapshot] = (
            update_database_step
        )
        self._read_database_step: SagaStep[ReadDatabaseInput, DatabaseFieldsSnapshot] = read_database_step

    def plan(self, *, cluster: ConfiguredCluster, spec: DatabaseSpec) -> SagaPlan:
        database: NewDatabase = spec.database
        users: list[DatabaseUserSpec] = spec.users
        steps: list[PreparableStep] = self._steps(
            address=address_of(cluster=cluster), database=database, users=users
        )
        logger.info(msg=f"database {database.name} on {cluster.name} plans {len(steps)} steps")
        return SagaPlan(
            steps=steps,
            lock_keys=creation_lock_keys(
                cluster_url=cluster.api_url,
                database_name=database.name,
                user_names=[user.name for user in users],
            ),
        )

    def _steps(
        self, *, address: ClusterAddress, database: NewDatabase, users: list[DatabaseUserSpec]
    ) -> list[PreparableStep]:
        return [
            self._database_step(address=address, database=database),
            *(
                step
                for user in users
                for step in self._steps_for_user(address=address, database=database, user=user)
            ),
            *self._permissions_steps(address=address, users=users),
            self._read_database_planned_step(address=address, users=users),
        ]

    def _database_step(self, *, address: ClusterAddress, database: NewDatabase) -> PreparableStep:
        return PlannedStep(
            key=DATABASE_STEP_KEY,
            step=self._create_database_step,
            build_input=partial(fixed_resource_input, address=address, spec=database),
        )

    def _steps_for_user(
        self, *, address: ClusterAddress, database: NewDatabase, user: DatabaseUserSpec
    ) -> list[PreparableStep]:
        return [
            self._acl_step(address=address, database=database, user=user),
            self._role_step(address=address, database=database, user=user),
            self._user_step(address=address, user=user),
        ]

    def _acl_step(
        self, *, address: ClusterAddress, database: NewDatabase, user: DatabaseUserSpec
    ) -> PreparableStep:
        acl_name: str = self._resource_naming.acl_name(database_name=database.name, user_name=user.name)
        acl: NewAcl = NewAcl(name=acl_name, acl=user.acl_rule)
        return PlannedStep(
            key=acl_step_key(user=user),
            step=self._create_acl_step,
            build_input=partial(fixed_resource_input, address=address, spec=acl),
        )

    def _role_step(
        self, *, address: ClusterAddress, database: NewDatabase, user: DatabaseUserSpec
    ) -> PreparableStep:
        role_name: str = self._resource_naming.role_name(database_name=database.name, user_name=user.name)
        return PlannedStep(
            key=role_step_key(user=user),
            step=self._create_role_step,
            build_input=partial(self._role_input, address=address, role_name=role_name),
        )

    def _role_input(
        self, *, step_results: StepResults, address: ClusterAddress, role_name: str
    ) -> CreateResourceInput[NewRole]:
        return CreateResourceInput(
            cluster=address,
            spec=NewRole(
                name=role_name,
                management=self._role_management,
                database_uids=[uid_created_by_step(step_results=step_results, step_key=DATABASE_STEP_KEY)],
            ),
        )

    def _user_step(self, *, address: ClusterAddress, user: DatabaseUserSpec) -> PreparableStep:
        return PlannedStep(
            key=user_step_key(user=user),
            step=self._create_user_step,
            build_input=partial(user_input, address=address, user=user),
        )

    def _permissions_steps(
        self, *, address: ClusterAddress, users: list[DatabaseUserSpec]
    ) -> list[PreparableStep]:
        if not users:
            return []
        return [
            PlannedStep(
                key=PERMISSIONS_STEP_KEY,
                step=self._update_database_step,
                build_input=partial(self._permissions_input, address=address, users=users),
            )
        ]

    def _read_database_planned_step(
        self, *, address: ClusterAddress, users: list[DatabaseUserSpec]
    ) -> PreparableStep:
        return PlannedStep(
            key=READ_DATABASE_STEP_KEY,
            step=self._read_database_step,
            build_input=partial(self._read_database_input, address=address, users=users),
        )

    def _read_database_input(
        self, *, step_results: StepResults, address: ClusterAddress, users: list[DatabaseUserSpec]
    ) -> ReadDatabaseInput:
        return ReadDatabaseInput(
            cluster=address,
            uid=uid_created_by_step(step_results=step_results, step_key=DATABASE_STEP_KEY),
            expected_values=self._permission_values(step_results=step_results, users=users) if users else {},
        )

    def _permissions_input(
        self, *, step_results: StepResults, address: ClusterAddress, users: list[DatabaseUserSpec]
    ) -> UpdateDatabaseInput:
        return UpdateDatabaseInput(
            cluster=address,
            uid=uid_created_by_step(step_results=step_results, step_key=DATABASE_STEP_KEY),
            values=self._permission_values(step_results=step_results, users=users),
        )

    def _permission_values(
        self, *, step_results: StepResults, users: list[DatabaseUserSpec]
    ) -> dict[str, JsonValue]:
        return {
            self._cluster_fields.roles_permissions: [
                permission.model_dump(mode="json")
                for permission in role_permissions(step_results=step_results, users=users)
            ]
        }


def fixed_resource_input[TSpec: NamedSpec](
    *, step_results: StepResults, address: ClusterAddress, spec: TSpec
) -> CreateResourceInput[TSpec]:
    return CreateResourceInput(cluster=address, spec=spec)


def user_input(
    *, step_results: StepResults, address: ClusterAddress, user: DatabaseUserSpec
) -> CreateResourceInput[NewUser]:
    return CreateResourceInput(
        cluster=address,
        spec=NewUser(
            name=user.name,
            password=user.password,
            role_uids=[uid_created_by_step(step_results=step_results, step_key=role_step_key(user=user))],
        ),
    )


def creation_lock_keys(*, cluster_url: str, database_name: str, user_names: list[str]) -> list[str]:
    return [
        f"{cluster_url}/{DATABASE_LOCK_SEGMENT}/{database_name}",
        *(f"{cluster_url}/{USER_LOCK_SEGMENT}/{user_name}" for user_name in user_names),
    ]


def role_permissions(*, step_results: StepResults, users: list[DatabaseUserSpec]) -> list[RolePermission]:
    return [
        RolePermission(
            role_uid=uid_created_by_step(step_results=step_results, step_key=role_step_key(user=user)),
            redis_acl_uid=uid_created_by_step(step_results=step_results, step_key=acl_step_key(user=user)),
        )
        for user in users
    ]


def uid_created_by_step(*, step_results: StepResults, step_key: str) -> int:
    return step_results.result_of(key=step_key, result_type=CreatedResource).uid
