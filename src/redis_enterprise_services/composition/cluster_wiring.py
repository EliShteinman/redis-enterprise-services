from pydantic import SecretStr

from redis_enterprise_services.acls.models import NewAcl
from redis_enterprise_services.acls.repository import AclRepository
from redis_enterprise_services.cluster.actions import ActionWaiter
from redis_enterprise_services.cluster.api import ClusterApi
from redis_enterprise_services.cluster.credentials import (
    ClusterCredentialsProvider,
    SharedCredentialsProvider,
)
from redis_enterprise_services.config.settings import Settings
from redis_enterprise_services.connection.models import ClusterCredentials
from redis_enterprise_services.databases.active_waiter import DatabaseActiveWaiter
from redis_enterprise_services.databases.lifecycle import DatabaseLifecycle
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.databases.repository import DatabaseRepository
from redis_enterprise_services.edge.client import EdgeClient
from redis_enterprise_services.edge.headers import EdgeHeaders
from redis_enterprise_services.edge.response_reader import EdgeResponseReader
from redis_enterprise_services.resources.action_completion import ActionCompletionWaiter
from redis_enterprise_services.resources.endpoint import ResourceEndpoint
from redis_enterprise_services.roles.models import NewRole
from redis_enterprise_services.roles.repository import RoleRepository
from redis_enterprise_services.steps.create_resource import CreateResourceStep
from redis_enterprise_services.steps.database_update import DatabaseUpdate
from redis_enterprise_services.users.models import NewUser
from redis_enterprise_services.users.repository import UserRepository


class ClusterWiring:
    def __init__(self, *, settings: Settings) -> None:
        edge: EdgeClient = EdgeClient(
            settings=settings.edge,
            headers=EdgeHeaders(settings=settings.edge),
            reader=EdgeResponseReader(settings=settings.edge),
        )
        api: ClusterApi = ClusterApi(transport=edge, settings=settings.cluster)
        password: SecretStr = settings.cluster_access.password
        self.credentials: ClusterCredentialsProvider = SharedCredentialsProvider(
            credentials=ClusterCredentials(username=settings.cluster_access.username, password=password)
        )
        self.databases: DatabaseLifecycle = DatabaseLifecycle(
            endpoint=ResourceEndpoint(api=api, settings=settings.database, cluster=settings.cluster),
            default_user_password=settings.database.default_user_password,
            default_tags=settings.database.default_tags,
        )
        self.acls: AclRepository = AclRepository(
            endpoint=ResourceEndpoint(api=api, settings=settings.acl, cluster=settings.cluster)
        )
        self.roles: RoleRepository = RoleRepository(
            endpoint=ResourceEndpoint(api=api, settings=settings.role, cluster=settings.cluster),
            settings=settings.role,
        )
        self.users: UserRepository = UserRepository(
            endpoint=ResourceEndpoint(api=api, settings=settings.user, cluster=settings.cluster)
        )
        fields: DatabaseRepository = DatabaseRepository(
            api=api, settings=settings.database, cluster=settings.cluster
        )
        database_waiter: DatabaseActiveWaiter = DatabaseActiveWaiter(
            fields=fields, settings=settings.database, cluster=settings.cluster
        )
        action_waiter: ActionCompletionWaiter = ActionCompletionWaiter(
            actions=ActionWaiter(api=api, settings=settings.action, cluster=settings.cluster)
        )
        self.create_database: CreateResourceStep[NewDatabase] = CreateResourceStep(
            repository=self.databases, waiter=database_waiter, credentials=self.credentials
        )
        self.create_acl: CreateResourceStep[NewAcl] = CreateResourceStep(
            repository=self.acls, waiter=action_waiter, credentials=self.credentials
        )
        self.create_role: CreateResourceStep[NewRole] = CreateResourceStep(
            repository=self.roles, waiter=action_waiter, credentials=self.credentials
        )
        self.create_user: CreateResourceStep[NewUser] = CreateResourceStep(
            repository=self.users, waiter=action_waiter, credentials=self.credentials
        )
        self.update_database: DatabaseUpdate = DatabaseUpdate(
            repository=fields, readiness=database_waiter, credentials=self.credentials
        )
