import logging

from redis_enterprise_services.acls.models import NewAcl
from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.config.cluster_api_settings import ClusterFieldSettings
from redis_enterprise_services.config.cluster_inventory import ClusterEntry
from redis_enterprise_services.config.role_management import RoleManagement
from redis_enterprise_services.config.user_resources_settings import UserResourcesSettings
from redis_enterprise_services.databases.models import DatabaseFields
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.planning.cluster_address import address_of
from redis_enterprise_services.planning.database_creation_request import DatabaseUserRequest
from redis_enterprise_services.planning.role_permission import RolePermission
from redis_enterprise_services.planning.user_resource_names import UserResourceNames
from redis_enterprise_services.resources.models import CreatedResource, CreateResourceInput
from redis_enterprise_services.roles.models import NewRole
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.plan.planned_step import PlannedStep
from redis_enterprise_services.saga.plan.saga_context import SagaContext
from redis_enterprise_services.saga.plan.saga_plan import SagaPlan
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep
from redis_enterprise_services.steps.update_database import UpdateDatabaseInput
from redis_enterprise_services.users.models import NewUser

logger: logging.Logger = logging.getLogger(name=__name__)

DATABASE_STEP_KEY: str = "database"
PERMISSIONS_STEP_KEY: str = "permissions"
USER_LOCK_SEGMENT: str = "user"


class SingleSiteCreationPlanner:
    def __init__(
        self,
        *,
        settings: UserResourcesSettings,
        fields: ClusterFieldSettings,
        resource_names: UserResourceNames,
        create_database: SagaStep[CreateResourceInput[NewDatabase], CreatedResource],
        create_acl: SagaStep[CreateResourceInput[NewAcl], CreatedResource],
        create_role: SagaStep[CreateResourceInput[NewRole], CreatedResource],
        create_user: SagaStep[CreateResourceInput[NewUser], CreatedResource],
        update_database: SagaStep[UpdateDatabaseInput, DatabaseFields],
    ) -> None:
        self._settings: UserResourcesSettings = settings
        self._fields: ClusterFieldSettings = fields
        self._resource_names: UserResourceNames = resource_names
        self._create_database: SagaStep[CreateResourceInput[NewDatabase], CreatedResource] = create_database
        self._create_acl: SagaStep[CreateResourceInput[NewAcl], CreatedResource] = create_acl
        self._create_role: SagaStep[CreateResourceInput[NewRole], CreatedResource] = create_role
        self._create_user: SagaStep[CreateResourceInput[NewUser], CreatedResource] = create_user
        self._update_database: SagaStep[UpdateDatabaseInput, DatabaseFields] = update_database

    def plan(
        self, *, cluster: ClusterEntry, database: NewDatabase, users: list[DatabaseUserRequest]
    ) -> SagaPlan:
        address: ClusterAddress = address_of(cluster=cluster)
        steps: list[PreparableStep] = [self._database_step(address=address, database=database)]
        for user in users:
            steps.extend(self._steps_for_user(address=address, database=database, user=user))
        if users:
            steps.append(self._permissions_step(address=address, users=users))
        logger.info(msg=f"database {database.name} on {cluster.name} plans {len(steps)} steps")
        return SagaPlan(
            steps=steps,
            lock_keys=[
                f"{cluster.name}/{database.name}",
                *(f"{cluster.name}/{USER_LOCK_SEGMENT}/{user.name}" for user in users),
            ],
        )

    def _database_step(self, *, address: ClusterAddress, database: NewDatabase) -> PreparableStep:
        return PlannedStep(
            key=DATABASE_STEP_KEY,
            step=self._create_database,
            build_input=lambda context: CreateResourceInput(cluster=address, spec=database),
        )

    def _steps_for_user(
        self, *, address: ClusterAddress, database: NewDatabase, user: DatabaseUserRequest
    ) -> list[PreparableStep]:
        return [
            self._acl_step(address=address, database=database, user=user),
            self._role_step(address=address, database=database, user=user),
            self._user_step(address=address, user=user),
        ]

    def _acl_step(
        self, *, address: ClusterAddress, database: NewDatabase, user: DatabaseUserRequest
    ) -> PreparableStep:
        acl_name: str = self._resource_names.acl(database=database.name, user=user.name)
        acl: NewAcl = NewAcl(name=acl_name, acl=user.acl)
        return PlannedStep(
            key=acl_step_key(user=user),
            step=self._create_acl,
            build_input=lambda context: CreateResourceInput(cluster=address, spec=acl),
        )

    def _role_step(
        self, *, address: ClusterAddress, database: NewDatabase, user: DatabaseUserRequest
    ) -> PreparableStep:
        role_name: str = self._resource_names.role(database=database.name, user=user.name)
        management: RoleManagement = self._settings.role_management
        return PlannedStep(
            key=role_step_key(user=user),
            step=self._create_role,
            build_input=lambda context: CreateResourceInput(
                cluster=address,
                spec=NewRole(
                    name=role_name,
                    management=management,
                    database_uids=[created_uid(context=context, step_key=DATABASE_STEP_KEY)],
                ),
            ),
        )

    def _user_step(self, *, address: ClusterAddress, user: DatabaseUserRequest) -> PreparableStep:
        return PlannedStep(
            key=user_step_key(user=user),
            step=self._create_user,
            build_input=lambda context: CreateResourceInput(
                cluster=address,
                spec=NewUser(
                    name=user.name,
                    password=user.password,
                    role_uids=[created_uid(context=context, step_key=role_step_key(user=user))],
                ),
            ),
        )

    def _permissions_step(
        self, *, address: ClusterAddress, users: list[DatabaseUserRequest]
    ) -> PreparableStep:
        return PlannedStep(
            key=PERMISSIONS_STEP_KEY,
            step=self._update_database,
            build_input=lambda context: UpdateDatabaseInput(
                cluster=address,
                uid=created_uid(context=context, step_key=DATABASE_STEP_KEY),
                values={
                    self._fields.roles_permissions: [
                        RolePermission(
                            role_uid=created_uid(context=context, step_key=role_step_key(user=user)),
                            redis_acl_uid=created_uid(context=context, step_key=acl_step_key(user=user)),
                        ).model_dump(mode="json")
                        for user in users
                    ]
                },
            ),
        )


def created_uid(*, context: SagaContext, step_key: str) -> int:
    return context.result_of(key=step_key, result_type=CreatedResource).uid


def acl_step_key(*, user: DatabaseUserRequest) -> str:
    return f"acl/{user.name}"


def role_step_key(*, user: DatabaseUserRequest) -> str:
    return f"role/{user.name}"


def user_step_key(*, user: DatabaseUserRequest) -> str:
    return f"user/{user.name}"
