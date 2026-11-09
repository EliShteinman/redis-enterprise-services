from pydantic import SecretStr

from redis_enterprise_services.acls.models import NewAcl
from redis_enterprise_services.cluster.cluster_target_resolver import (
    ClusterTargetResolver,
    SharedCredentialsTargetResolver,
)
from redis_enterprise_services.cluster.edge_cluster_api_caller import EdgeClusterApiCaller
from redis_enterprise_services.cluster.polling_action_waiter import PollingActionWaiter
from redis_enterprise_services.cluster.read_again_polling import ReadAgainPolling
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
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
from redis_enterprise_services.resources.creation_body_builder import SpecCreationBody
from redis_enterprise_services.resources.endpoint_resource_repository import EndpointResourceRepository
from redis_enterprise_services.resources.rest_resource_endpoint import RestResourceEndpoint
from redis_enterprise_services.roles.models import NewRole
from redis_enterprise_services.roles.role_creation_body_builder import RoleCreationBodyBuilder
from redis_enterprise_services.steps.create_resource import CreateResourceStep
from redis_enterprise_services.steps.update_database import UpdateDatabaseStep
from redis_enterprise_services.timing.clock import MonotonicClock
from redis_enterprise_services.timing.deadline_polling import DeadlinePolling
from redis_enterprise_services.timing.sleeper import SystemSleeper
from redis_enterprise_services.users.models import NewUser


class ClusterWiring:
    def __init__(self, *, settings: Settings) -> None:
        edge_transport: EdgeClient = EdgeClient(
            settings=settings.edge,
            header_builder=EdgeHeaderBuilder(settings=settings.edge),
            response_reader=EdgeResponseReader(settings=settings.edge),
        )
        cluster_api_caller: EdgeClusterApiCaller = EdgeClusterApiCaller(
            edge_transport=edge_transport, settings=settings.cluster_api
        )
        cluster_password: SecretStr = settings.cluster_credentials.password
        self.target_resolver: ClusterTargetResolver = SharedCredentialsTargetResolver(
            credentials=ClusterCredentials(
                username=settings.cluster_credentials.username, password=cluster_password
            )
        )
        self.database_repository: EndpointResourceRepository[NewDatabase] = EndpointResourceRepository(
            endpoint=self._endpoint(
                cluster_api_caller=cluster_api_caller, settings=settings, resource=settings.database
            ),
            body_builder=DatabaseCreationBodyBuilder(
                default_user_password=settings.database.default_user_password,
                default_tags=settings.database.default_tags,
            ),
        )
        self.acl_repository: EndpointResourceRepository[NewAcl] = EndpointResourceRepository(
            endpoint=self._endpoint(
                cluster_api_caller=cluster_api_caller, settings=settings, resource=settings.acl
            ),
            body_builder=SpecCreationBody[NewAcl](),
        )
        self.role_repository: EndpointResourceRepository[NewRole] = EndpointResourceRepository(
            endpoint=self._endpoint(
                cluster_api_caller=cluster_api_caller, settings=settings, resource=settings.role
            ),
            body_builder=RoleCreationBodyBuilder(settings=settings.role),
        )
        self.user_repository: EndpointResourceRepository[NewUser] = EndpointResourceRepository(
            endpoint=self._endpoint(
                cluster_api_caller=cluster_api_caller, settings=settings, resource=settings.user
            ),
            body_builder=SpecCreationBody[NewUser](),
        )
        read_again_polling: ReadAgainPolling = ReadAgainPolling(
            deadline_polling=DeadlinePolling(clock=MonotonicClock(), sleeper=SystemSleeper()),
            transient_error_codes=settings.cluster_api.transient_error_codes,
        )
        database_fields_repository: RestDatabaseFieldsRepository = RestDatabaseFieldsRepository(
            cluster_api_caller=cluster_api_caller,
            settings=settings.database,
            cluster_api_settings=settings.cluster_api,
        )
        polling_database_waiter: PollingDatabaseWaiter = PollingDatabaseWaiter(
            fields_reader=database_fields_repository,
            read_again_polling=read_again_polling,
            settings=settings.database,
            cluster_api_settings=settings.cluster_api,
        )
        action_completion_waiter: ActionCompletionWaiter = ActionCompletionWaiter(
            action_waiter=PollingActionWaiter(
                cluster_api_caller=cluster_api_caller,
                read_again_polling=read_again_polling,
                settings=settings.action,
                cluster_api_settings=settings.cluster_api,
            )
        )
        self.create_database_step: CreateResourceStep[NewDatabase] = CreateResourceStep(
            repository=self.database_repository,
            completion_waiter=polling_database_waiter,
            target_resolver=self.target_resolver,
        )
        self.create_acl_step: CreateResourceStep[NewAcl] = CreateResourceStep(
            repository=self.acl_repository,
            completion_waiter=action_completion_waiter,
            target_resolver=self.target_resolver,
        )
        self.create_role_step: CreateResourceStep[NewRole] = CreateResourceStep(
            repository=self.role_repository,
            completion_waiter=action_completion_waiter,
            target_resolver=self.target_resolver,
        )
        self.create_user_step: CreateResourceStep[NewUser] = CreateResourceStep(
            repository=self.user_repository,
            completion_waiter=action_completion_waiter,
            target_resolver=self.target_resolver,
        )
        self.update_database_step: UpdateDatabaseStep = UpdateDatabaseStep(
            repository=database_fields_repository,
            activation_waiter=polling_database_waiter,
            target_resolver=self.target_resolver,
            order_insensitive_fields=settings.database.order_insensitive_fields,
        )

    @staticmethod
    def _endpoint(
        *, cluster_api_caller: EdgeClusterApiCaller, settings: Settings, resource: ResourceSettings
    ) -> RestResourceEndpoint:
        return RestResourceEndpoint(
            cluster_api_caller=cluster_api_caller,
            settings=resource,
            cluster_api_settings=settings.cluster_api,
        )
