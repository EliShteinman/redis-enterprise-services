import logging

from redis_enterprise_services.acls.models import NewAcl
from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.config.clusters_settings import ClusterEntry
from redis_enterprise_services.config.decomposition_settings import DecompositionSettings
from redis_enterprise_services.config.role_management import RoleManagement
from redis_enterprise_services.databases.models import DatabaseFields
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.planning.database_request import DatabaseUserRequest
from redis_enterprise_services.resources.models import CreatedResource, CreateResourceInput
from redis_enterprise_services.roles.models import NewRole
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.plan.context import SagaContext
from redis_enterprise_services.saga.plan.planned_step import PlannedStep
from redis_enterprise_services.saga.plan.runnable import RunnableStep
from redis_enterprise_services.saga.plan.saga_plan import SagaPlan
from redis_enterprise_services.steps.database_update import DatabaseUpdateInput
from redis_enterprise_services.users.models import NewUser

logger: logging.Logger = logging.getLogger(name=__name__)

DATABASE_KEY: str = "database"
PERMISSIONS_KEY: str = "permissions"


class SingleSiteCreationPlanner:
    def __init__(
        self,
        *,
        settings: DecompositionSettings,
        create_database: SagaStep[CreateResourceInput[NewDatabase], CreatedResource],
        create_acl: SagaStep[CreateResourceInput[NewAcl], CreatedResource],
        create_role: SagaStep[CreateResourceInput[NewRole], CreatedResource],
        create_user: SagaStep[CreateResourceInput[NewUser], CreatedResource],
        update_database: SagaStep[DatabaseUpdateInput, DatabaseFields],
    ) -> None:
        self._settings: DecompositionSettings = settings
        self._create_database: SagaStep[CreateResourceInput[NewDatabase], CreatedResource] = create_database
        self._create_acl: SagaStep[CreateResourceInput[NewAcl], CreatedResource] = create_acl
        self._create_role: SagaStep[CreateResourceInput[NewRole], CreatedResource] = create_role
        self._create_user: SagaStep[CreateResourceInput[NewUser], CreatedResource] = create_user
        self._update_database: SagaStep[DatabaseUpdateInput, DatabaseFields] = update_database

    def plan(
        self, *, cluster: ClusterEntry, database: NewDatabase, users: list[DatabaseUserRequest]
    ) -> SagaPlan:
        address: ClusterAddress = ClusterAddress(network=cluster.network, api_url=cluster.api_url)
        steps: list[RunnableStep] = [self._database_step(address=address, database=database)]
        for user in users:
            steps.extend(self._user_steps(address=address, database=database, user=user))
        if users:
            steps.append(self._permissions_step(address=address, users=users))
        logger.info(msg=f"database {database.name} on {cluster.name} plans {len(steps)} steps")
        return SagaPlan(steps=steps, lock_keys=[f"{cluster.name}/{database.name}"])

    def _database_step(self, *, address: ClusterAddress, database: NewDatabase) -> RunnableStep:
        return PlannedStep(
            key=DATABASE_KEY,
            step=self._create_database,
            build_input=lambda context: CreateResourceInput(cluster=address, spec=database),
        )

    def _user_steps(
        self, *, address: ClusterAddress, database: NewDatabase, user: DatabaseUserRequest
    ) -> list[RunnableStep]:
        acl_name: str = self._name(template=self._settings.acl_name, database=database, user=user)
        acl: NewAcl = NewAcl(name=acl_name, acl=user.acl)
        role_name: str = self._name(template=self._settings.role_name, database=database, user=user)
        management: RoleManagement = self._settings.role_management
        return [
            PlannedStep(
                key=acl_key(user=user),
                step=self._create_acl,
                build_input=lambda context: CreateResourceInput(cluster=address, spec=acl),
            ),
            PlannedStep(
                key=role_key(user=user),
                step=self._create_role,
                build_input=lambda context: CreateResourceInput(
                    cluster=address,
                    spec=NewRole(
                        name=role_name,
                        management=management,
                        database_uids=[uid_of(context=context, key=DATABASE_KEY)],
                    ),
                ),
            ),
            PlannedStep(
                key=user_key(user=user),
                step=self._create_user,
                build_input=lambda context: CreateResourceInput(
                    cluster=address,
                    spec=NewUser(
                        name=user.name,
                        password=user.password,
                        role_uids=[uid_of(context=context, key=role_key(user=user))],
                    ),
                ),
            ),
        ]

    def _permissions_step(self, *, address: ClusterAddress, users: list[DatabaseUserRequest]) -> RunnableStep:
        return PlannedStep(
            key=PERMISSIONS_KEY,
            step=self._update_database,
            build_input=lambda context: DatabaseUpdateInput(
                cluster=address,
                uid=uid_of(context=context, key=DATABASE_KEY),
                values={
                    "roles_permissions": [
                        {
                            "role_uid": uid_of(context=context, key=role_key(user=user)),
                            "redis_acl_uid": uid_of(context=context, key=acl_key(user=user)),
                        }
                        for user in users
                    ]
                },
            ),
        )

    @staticmethod
    def _name(*, template: str, database: NewDatabase, user: DatabaseUserRequest) -> str:
        return template.format(database=database.name, user=user.name)


def uid_of(*, context: SagaContext, key: str) -> int:
    return context.result_of(key=key, result_type=CreatedResource).uid


def acl_key(*, user: DatabaseUserRequest) -> str:
    return f"acl/{user.name}"


def role_key(*, user: DatabaseUserRequest) -> str:
    return f"role/{user.name}"


def user_key(*, user: DatabaseUserRequest) -> str:
    return f"user/{user.name}"
