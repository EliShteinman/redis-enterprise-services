from redis_enterprise_services.acls.models import NewAcl
from redis_enterprise_services.cluster.cluster_target_resolver import ClusterTargetResolver
from redis_enterprise_services.composition.cluster_repositories import ClusterRepositories
from redis_enterprise_services.composition.cluster_waiters import ClusterWaiters
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.roles.models import NewRole
from redis_enterprise_services.steps.create_resource import CreateResourceStep
from redis_enterprise_services.steps.read_database import ReadDatabaseStep
from redis_enterprise_services.steps.update_database import UpdateDatabaseStep
from redis_enterprise_services.users.models import NewUser


class ClusterSteps:
    def __init__(
        self,
        *,
        create_database: CreateResourceStep[NewDatabase],
        create_acl: CreateResourceStep[NewAcl],
        create_role: CreateResourceStep[NewRole],
        create_user: CreateResourceStep[NewUser],
        update_database: UpdateDatabaseStep,
        read_database: ReadDatabaseStep,
    ) -> None:
        self.create_database: CreateResourceStep[NewDatabase] = create_database
        self.create_acl: CreateResourceStep[NewAcl] = create_acl
        self.create_role: CreateResourceStep[NewRole] = create_role
        self.create_user: CreateResourceStep[NewUser] = create_user
        self.update_database: UpdateDatabaseStep = update_database
        self.read_database: ReadDatabaseStep = read_database


def build_cluster_steps(
    *,
    database: DatabaseSettings,
    repositories: ClusterRepositories,
    waiters: ClusterWaiters,
    target_resolver: ClusterTargetResolver,
) -> ClusterSteps:
    return ClusterSteps(
        create_database=CreateResourceStep(
            repository=repositories.database,
            completion_waiter=waiters.database,
            target_resolver=target_resolver,
        ),
        create_acl=CreateResourceStep(
            repository=repositories.acl,
            completion_waiter=waiters.action_completion,
            target_resolver=target_resolver,
        ),
        create_role=CreateResourceStep(
            repository=repositories.role,
            completion_waiter=waiters.action_completion,
            target_resolver=target_resolver,
        ),
        create_user=CreateResourceStep(
            repository=repositories.user,
            completion_waiter=waiters.action_completion,
            target_resolver=target_resolver,
        ),
        update_database=UpdateDatabaseStep(
            repository=repositories.database_fields,
            activation_waiter=waiters.database,
            target_resolver=target_resolver,
            order_insensitive_fields=database.order_insensitive_fields,
        ),
        read_database=ReadDatabaseStep(
            fields_reader=repositories.database_fields, target_resolver=target_resolver, settings=database
        ),
    )
