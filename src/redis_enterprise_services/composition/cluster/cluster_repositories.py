from redis_enterprise_services.acls.models import NewAcl
from redis_enterprise_services.cluster.edge_cluster_api_caller import EdgeClusterApiCaller
from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.redis_api.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.config.redis_api.crdb_settings import CrdbSettings
from redis_enterprise_services.config.redis_api.database_settings import DatabaseSettings
from redis_enterprise_services.config.redis_api.resource_settings import ResourceSettings
from redis_enterprise_services.config.redis_api.role_settings import RoleSettings
from redis_enterprise_services.crdbs.rest_crdb_repository import RestCrdbRepository
from redis_enterprise_services.databases.database_creation_body_builder import DatabaseCreationBodyBuilder
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.databases.rest_database_fields_repository import RestDatabaseFieldsRepository
from redis_enterprise_services.resources.creation_body_builder import CreationBodyBuilder, SpecCreationBody
from redis_enterprise_services.resources.endpoint.endpoint_resource_repository import (
    EndpointResourceRepository,
)
from redis_enterprise_services.resources.endpoint.rest_resource_endpoint import RestResourceEndpoint
from redis_enterprise_services.resources.named_spec import NamedSpec
from redis_enterprise_services.roles.models import NewRole
from redis_enterprise_services.roles.role_creation_body_builder import RoleCreationBodyBuilder
from redis_enterprise_services.users.models import NewUser


class ClusterRepositories:
    def __init__(
        self,
        *,
        database: EndpointResourceRepository[NewDatabase],
        acl: EndpointResourceRepository[NewAcl],
        role: EndpointResourceRepository[NewRole],
        user: EndpointResourceRepository[NewUser],
        database_fields: RestDatabaseFieldsRepository,
        database_body_builder: DatabaseCreationBodyBuilder,
        crdb: RestCrdbRepository,
    ) -> None:
        self.database: EndpointResourceRepository[NewDatabase] = database
        self.database_body_builder: DatabaseCreationBodyBuilder = database_body_builder
        self.crdb: RestCrdbRepository = crdb
        self.database_fields: RestDatabaseFieldsRepository = database_fields
        self.acl: EndpointResourceRepository[NewAcl] = acl
        self.role: EndpointResourceRepository[NewRole] = role
        self.user: EndpointResourceRepository[NewUser] = user


def build_cluster_repositories(
    *,
    cluster_api: ClusterApiSettings,
    database: DatabaseSettings,
    acl: ResourceSettings,
    role: RoleSettings,
    user: ResourceSettings,
    crdb: CrdbSettings,
    clusters: list[ConfiguredCluster],
    cluster_api_caller: EdgeClusterApiCaller,
) -> ClusterRepositories:
    database_body_builder: DatabaseCreationBodyBuilder = build_database_body_builder(
        database=database, clusters=clusters
    )
    return ClusterRepositories(
        database=rest_repository(
            cluster_api_caller=cluster_api_caller,
            cluster_api=cluster_api,
            resource=database,
            body_builder=database_body_builder,
        ),
        database_body_builder=database_body_builder,
        crdb=RestCrdbRepository(
            cluster_api_caller=cluster_api_caller, database_body_builder=database_body_builder, settings=crdb
        ),
        acl=rest_repository(
            cluster_api_caller=cluster_api_caller,
            cluster_api=cluster_api,
            resource=acl,
            body_builder=SpecCreationBody[NewAcl](),
        ),
        role=rest_repository(
            cluster_api_caller=cluster_api_caller,
            cluster_api=cluster_api,
            resource=role,
            body_builder=RoleCreationBodyBuilder(settings=role),
        ),
        user=rest_repository(
            cluster_api_caller=cluster_api_caller,
            cluster_api=cluster_api,
            resource=user,
            body_builder=SpecCreationBody[NewUser](),
        ),
        database_fields=RestDatabaseFieldsRepository(
            cluster_api_caller=cluster_api_caller, settings=database
        ),
    )


def build_database_body_builder(
    *, database: DatabaseSettings, clusters: list[ConfiguredCluster]
) -> DatabaseCreationBodyBuilder:
    return DatabaseCreationBodyBuilder(
        default_user_password_by_api_url={
            cluster.api_url: cluster.default_user_password for cluster in clusters
        },
        default_tags=database.default_tags,
    )


def rest_repository[TSpec: NamedSpec](
    *,
    cluster_api_caller: EdgeClusterApiCaller,
    cluster_api: ClusterApiSettings,
    resource: ResourceSettings,
    body_builder: CreationBodyBuilder[TSpec],
) -> EndpointResourceRepository[TSpec]:
    return EndpointResourceRepository(
        endpoint=RestResourceEndpoint(
            cluster_api_caller=cluster_api_caller, settings=resource, cluster_api_settings=cluster_api
        ),
        body_builder=body_builder,
        unreturned_fields=frozenset(resource.unreturned_fields),
        secret_fields=frozenset(resource.secret_fields),
    )
