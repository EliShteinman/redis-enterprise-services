from redis_enterprise_services.acls.models import NewAcl
from redis_enterprise_services.cluster.cluster_target_resolver import (
    ClusterTargetResolver,
    SharedCredentialsTargetResolver,
)
from redis_enterprise_services.cluster.edge_cluster_api_caller import EdgeClusterApiCaller
from redis_enterprise_services.cluster.polling_action_waiter import PollingActionWaiter
from redis_enterprise_services.cluster.read_again_polling import ReadAgainPolling
from redis_enterprise_services.cluster.status_polling import StatusPolling
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.config.resource_settings import ResourceSettings
from redis_enterprise_services.config.settings import Settings
from redis_enterprise_services.databases.database_creation_body_builder import DatabaseCreationBodyBuilder
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.databases.polling_database_waiter import PollingDatabaseWaiter
from redis_enterprise_services.databases.rest_database_fields_repository import RestDatabaseFieldsRepository
from redis_enterprise_services.edge.client import EdgeClient
from redis_enterprise_services.edge.header_builder import EdgeHeaderBuilder
from redis_enterprise_services.edge.response_reader import EdgeResponseReader
from redis_enterprise_services.resources.action_completion_waiter import ActionCompletionWaiter
from redis_enterprise_services.resources.creation_body_builder import CreationBodyBuilder, SpecCreationBody
from redis_enterprise_services.resources.endpoint_resource_repository import EndpointResourceRepository
from redis_enterprise_services.resources.named_spec import NamedSpec
from redis_enterprise_services.resources.rest_resource_endpoint import RestResourceEndpoint
from redis_enterprise_services.roles.models import NewRole
from redis_enterprise_services.roles.role_creation_body_builder import RoleCreationBodyBuilder
from redis_enterprise_services.steps.create_resource import CreateResourceStep
from redis_enterprise_services.steps.read_database import ReadDatabaseStep
from redis_enterprise_services.steps.update_database import UpdateDatabaseStep
from redis_enterprise_services.timing.deadline_polling import DeadlinePolling
from redis_enterprise_services.users.models import NewUser


class ClusterWiring:
    def __init__(self, *, settings: Settings, deadline_polling: DeadlinePolling) -> None:
        cluster_api_caller: EdgeClusterApiCaller = build_cluster_api_caller(settings=settings)
        read_again_polling: ReadAgainPolling = ReadAgainPolling(
            deadline_polling=deadline_polling,
            transient_error_codes=settings.cluster_api.transient_error_codes,
        )
        self.target_resolver: ClusterTargetResolver = build_target_resolver(settings=settings)
        self.repositories: ClusterRepositories = build_cluster_repositories(
            settings=settings, cluster_api_caller=cluster_api_caller
        )
        self.steps: ClusterSteps = ClusterSteps(
            settings=settings,
            cluster_api_caller=cluster_api_caller,
            read_again_polling=read_again_polling,
            target_resolver=self.target_resolver,
            repositories=self.repositories,
        )


class ClusterRepositories:
    def __init__(
        self,
        *,
        database: EndpointResourceRepository[NewDatabase],
        acl: EndpointResourceRepository[NewAcl],
        role: EndpointResourceRepository[NewRole],
        user: EndpointResourceRepository[NewUser],
        database_fields: RestDatabaseFieldsRepository,
    ) -> None:
        self.database: EndpointResourceRepository[NewDatabase] = database
        self.database_fields: RestDatabaseFieldsRepository = database_fields
        self.acl: EndpointResourceRepository[NewAcl] = acl
        self.role: EndpointResourceRepository[NewRole] = role
        self.user: EndpointResourceRepository[NewUser] = user


class ClusterSteps:
    def __init__(
        self,
        *,
        settings: Settings,
        cluster_api_caller: EdgeClusterApiCaller,
        read_again_polling: ReadAgainPolling,
        target_resolver: ClusterTargetResolver,
        repositories: ClusterRepositories,
    ) -> None:
        status_polling: StatusPolling = StatusPolling(
            read_again_polling=read_again_polling, status_field=settings.cluster_api.fields.status
        )
        database_waiter: PollingDatabaseWaiter = PollingDatabaseWaiter(
            fields_reader=repositories.database_fields,
            read_again_polling=read_again_polling,
            status_polling=status_polling,
            settings=settings.database,
        )
        action_completion_waiter: ActionCompletionWaiter = build_action_completion_waiter(
            settings=settings, cluster_api_caller=cluster_api_caller, status_polling=status_polling
        )
        self.create_database: CreateResourceStep[NewDatabase] = CreateResourceStep(
            repository=repositories.database,
            completion_waiter=database_waiter,
            target_resolver=target_resolver,
        )
        self.create_acl: CreateResourceStep[NewAcl] = CreateResourceStep(
            repository=repositories.acl,
            completion_waiter=action_completion_waiter,
            target_resolver=target_resolver,
        )
        self.create_role: CreateResourceStep[NewRole] = CreateResourceStep(
            repository=repositories.role,
            completion_waiter=action_completion_waiter,
            target_resolver=target_resolver,
        )
        self.create_user: CreateResourceStep[NewUser] = CreateResourceStep(
            repository=repositories.user,
            completion_waiter=action_completion_waiter,
            target_resolver=target_resolver,
        )
        self.update_database: UpdateDatabaseStep = UpdateDatabaseStep(
            repository=repositories.database_fields,
            activation_waiter=database_waiter,
            target_resolver=target_resolver,
            order_insensitive_fields=settings.database.order_insensitive_fields,
        )
        self.read_database: ReadDatabaseStep = ReadDatabaseStep(
            fields_reader=repositories.database_fields,
            target_resolver=target_resolver,
            settings=settings.database,
        )


def build_cluster_repositories(
    *, settings: Settings, cluster_api_caller: EdgeClusterApiCaller
) -> ClusterRepositories:
    return ClusterRepositories(
        database=build_database_repository(settings=settings, cluster_api_caller=cluster_api_caller),
        acl=rest_repository(
            cluster_api_caller=cluster_api_caller,
            cluster_api_settings=settings.cluster_api,
            resource=settings.acl,
            body_builder=SpecCreationBody[NewAcl](),
        ),
        role=rest_repository(
            cluster_api_caller=cluster_api_caller,
            cluster_api_settings=settings.cluster_api,
            resource=settings.role,
            body_builder=RoleCreationBodyBuilder(settings=settings.role),
        ),
        user=rest_repository(
            cluster_api_caller=cluster_api_caller,
            cluster_api_settings=settings.cluster_api,
            resource=settings.user,
            body_builder=SpecCreationBody[NewUser](),
        ),
        database_fields=RestDatabaseFieldsRepository(
            cluster_api_caller=cluster_api_caller,
            settings=settings.database,
            cluster_api_settings=settings.cluster_api,
        ),
    )


def build_cluster_api_caller(*, settings: Settings) -> EdgeClusterApiCaller:
    edge_transport: EdgeClient = EdgeClient(
        settings=settings.edge,
        header_builder=EdgeHeaderBuilder(settings=settings.edge),
        response_reader=EdgeResponseReader(settings=settings.edge),
    )
    return EdgeClusterApiCaller(edge_transport=edge_transport, settings=settings.cluster_api)


def build_target_resolver(*, settings: Settings) -> ClusterTargetResolver:
    return SharedCredentialsTargetResolver(
        credentials=ClusterCredentials(
            username=settings.cluster_credentials.username, password=settings.cluster_credentials.password
        )
    )


def build_action_completion_waiter(
    *, settings: Settings, cluster_api_caller: EdgeClusterApiCaller, status_polling: StatusPolling
) -> ActionCompletionWaiter:
    return ActionCompletionWaiter(
        action_waiter=PollingActionWaiter(
            cluster_api_caller=cluster_api_caller, status_polling=status_polling, settings=settings.action
        )
    )


def build_database_repository(
    *, settings: Settings, cluster_api_caller: EdgeClusterApiCaller
) -> EndpointResourceRepository[NewDatabase]:
    return rest_repository(
        cluster_api_caller=cluster_api_caller,
        cluster_api_settings=settings.cluster_api,
        resource=settings.database,
        body_builder=DatabaseCreationBodyBuilder(
            default_user_password=settings.database.default_user_password,
            default_tags=settings.database.default_tags,
        ),
    )


def rest_repository[TSpec: NamedSpec](
    *,
    cluster_api_caller: EdgeClusterApiCaller,
    cluster_api_settings: ClusterApiSettings,
    resource: ResourceSettings,
    body_builder: CreationBodyBuilder[TSpec],
) -> EndpointResourceRepository[TSpec]:
    return EndpointResourceRepository(
        endpoint=RestResourceEndpoint(
            cluster_api_caller=cluster_api_caller,
            settings=resource,
            cluster_api_settings=cluster_api_settings,
        ),
        body_builder=body_builder,
        unreturned_fields=frozenset(resource.unreturned_fields),
        secret_fields=frozenset(resource.secret_fields),
    )
