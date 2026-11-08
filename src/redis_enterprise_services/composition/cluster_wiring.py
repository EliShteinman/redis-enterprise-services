from pydantic import SecretStr

from redis_enterprise_services.acls.models import NewAcl
from redis_enterprise_services.acls.repository import AclRepository
from redis_enterprise_services.cluster.api import ClusterApi
from redis_enterprise_services.cluster.cluster_target_resolver import (
    ClusterTargetResolver,
    SharedCredentialsTargetResolver,
)
from redis_enterprise_services.cluster.polling_action_waiter import PollingActionWaiter
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.settings import Settings
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.databases.polling_database_waiter import PollingDatabaseWaiter
from redis_enterprise_services.databases.repository import DatabaseRepository
from redis_enterprise_services.databases.rest_database_fields_repository import RestDatabaseFieldsRepository
from redis_enterprise_services.edge.client import EdgeClient
from redis_enterprise_services.edge.header_builder import EdgeHeaderBuilder
from redis_enterprise_services.edge.response_reader import EdgeResponseReader
from redis_enterprise_services.resources.action_completion_waiter import ActionCompletionWaiter
from redis_enterprise_services.resources.rest_resource_endpoint import RestResourceEndpoint
from redis_enterprise_services.roles.models import NewRole
from redis_enterprise_services.roles.repository import RoleRepository
from redis_enterprise_services.steps.create_resource import CreateResourceStep
from redis_enterprise_services.steps.update_database import UpdateDatabaseStep
from redis_enterprise_services.users.models import NewUser
from redis_enterprise_services.users.repository import UserRepository


class ClusterWiring:
    def __init__(self, *, settings: Settings) -> None:
        edge: EdgeClient = EdgeClient(
            settings=settings.edge,
            header_builder=EdgeHeaderBuilder(settings=settings.edge),
            response_reader=EdgeResponseReader(settings=settings.edge),
        )
        api: ClusterApi = ClusterApi(transport=edge, settings=settings.cluster_api)
        password: SecretStr = settings.cluster_credentials.password
        self.target_resolver: ClusterTargetResolver = SharedCredentialsTargetResolver(
            credentials=ClusterCredentials(username=settings.cluster_credentials.username, password=password)
        )
        self.database_repository: DatabaseRepository = DatabaseRepository(
            endpoint=RestResourceEndpoint(
                api=api, settings=settings.database, cluster_api=settings.cluster_api
            ),
            default_user_password=settings.database.default_user_password,
            default_tags=settings.database.default_tags,
        )
        self.acl_repository: AclRepository = AclRepository(
            endpoint=RestResourceEndpoint(api=api, settings=settings.acl, cluster_api=settings.cluster_api)
        )
        self.role_repository: RoleRepository = RoleRepository(
            endpoint=RestResourceEndpoint(api=api, settings=settings.role, cluster_api=settings.cluster_api),
            settings=settings.role,
        )
        self.user_repository: UserRepository = UserRepository(
            endpoint=RestResourceEndpoint(api=api, settings=settings.user, cluster_api=settings.cluster_api)
        )
        database_fields_repository: RestDatabaseFieldsRepository = RestDatabaseFieldsRepository(
            api=api, settings=settings.database, cluster_api=settings.cluster_api
        )
        database_waiter: PollingDatabaseWaiter = PollingDatabaseWaiter(
            fields_reader=database_fields_repository,
            settings=settings.database,
            cluster_api=settings.cluster_api,
        )
        action_completion_waiter: ActionCompletionWaiter = ActionCompletionWaiter(
            action_waiter=PollingActionWaiter(
                api=api, settings=settings.action, cluster_api=settings.cluster_api
            )
        )
        self.create_database: CreateResourceStep[NewDatabase] = CreateResourceStep(
            repository=self.database_repository,
            completion_waiter=database_waiter,
            target_resolver=self.target_resolver,
        )
        self.create_acl: CreateResourceStep[NewAcl] = CreateResourceStep(
            repository=self.acl_repository,
            completion_waiter=action_completion_waiter,
            target_resolver=self.target_resolver,
        )
        self.create_role: CreateResourceStep[NewRole] = CreateResourceStep(
            repository=self.role_repository,
            completion_waiter=action_completion_waiter,
            target_resolver=self.target_resolver,
        )
        self.create_user: CreateResourceStep[NewUser] = CreateResourceStep(
            repository=self.user_repository,
            completion_waiter=action_completion_waiter,
            target_resolver=self.target_resolver,
        )
        self.update_database: UpdateDatabaseStep = UpdateDatabaseStep(
            repository=database_fields_repository,
            activation_waiter=database_waiter,
            target_resolver=self.target_resolver,
            unordered_fields=settings.database.unordered_fields,
        )
