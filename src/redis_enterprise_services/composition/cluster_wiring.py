import requests

from redis_enterprise_services.cluster.cluster_target_resolver import (
    ClusterTargetResolver,
    ConfiguredCredentialsTargetResolver,
)
from redis_enterprise_services.cluster.edge_cluster_api_caller import EdgeClusterApiCaller
from redis_enterprise_services.cluster.read_again_polling import ReadAgainPolling
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.composition.cluster_repositories import (
    ClusterRepositories,
    build_cluster_repositories,
)
from redis_enterprise_services.composition.cluster_steps import ClusterSteps, build_cluster_steps
from redis_enterprise_services.composition.cluster_waiters import ClusterWaiters, build_cluster_waiters
from redis_enterprise_services.composition.crdb_steps import CrdbSteps, build_crdb_steps
from redis_enterprise_services.config.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.edge_settings import EdgeSettings
from redis_enterprise_services.config.settings import Settings
from redis_enterprise_services.edge.client import EdgeClient
from redis_enterprise_services.edge.header_builder import EdgeHeaderBuilder
from redis_enterprise_services.edge.response_reader import EdgeResponseReader
from redis_enterprise_services.edge.session_without_cookies import session_without_cookies
from redis_enterprise_services.timing.deadline_polling import DeadlinePolling


class ClusterWiring:
    def __init__(
        self, *, settings: Settings, clusters: list[ConfiguredCluster], deadline_polling: DeadlinePolling
    ) -> None:
        self._edge_session: requests.Session = session_without_cookies()
        cluster_api_caller: EdgeClusterApiCaller = build_cluster_api_caller(
            edge=settings.edge, cluster_api=settings.cluster_api, edge_session=self._edge_session
        )
        self.target_resolver: ClusterTargetResolver = build_target_resolver(clusters=clusters)
        self.repositories: ClusterRepositories = build_cluster_repositories(
            cluster_api=settings.cluster_api,
            database=settings.database,
            acl=settings.acl,
            role=settings.role,
            user=settings.user,
            crdb=settings.crdb,
            clusters=clusters,
            cluster_api_caller=cluster_api_caller,
        )
        waiters: ClusterWaiters = build_cluster_waiters(
            database=settings.database,
            action=settings.action,
            crdb_task=settings.crdb.task,
            status_field=settings.cluster_api.fields.status,
            cluster_api_caller=cluster_api_caller,
            read_again_polling=ReadAgainPolling(
                deadline_polling=deadline_polling,
                transient_error_codes=settings.cluster_api.transient_error_codes,
            ),
            database_fields=self.repositories.database_fields,
        )
        self.steps: ClusterSteps = build_cluster_steps(
            database=settings.database,
            repositories=self.repositories,
            waiters=waiters,
            target_resolver=self.target_resolver,
        )
        self.crdb_steps: CrdbSteps = build_crdb_steps(
            crdb=settings.crdb,
            database=settings.database,
            repository=self.repositories.crdb,
            waiters=waiters,
            target_resolver=self.target_resolver,
        )

    def close(self) -> None:
        self._edge_session.close()


def build_cluster_api_caller(
    *, edge: EdgeSettings, cluster_api: ClusterApiSettings, edge_session: requests.Session
) -> EdgeClusterApiCaller:
    edge_transport: EdgeClient = EdgeClient(
        settings=edge,
        session=edge_session,
        header_builder=EdgeHeaderBuilder(settings=edge),
        response_reader=EdgeResponseReader(settings=edge),
    )
    return EdgeClusterApiCaller(edge_transport=edge_transport, settings=cluster_api)


def build_target_resolver(*, clusters: list[ConfiguredCluster]) -> ClusterTargetResolver:
    return ConfiguredCredentialsTargetResolver(
        credentials_by_api_url={
            cluster.api_url: ClusterCredentials(
                username=cluster.credentials.username, password=cluster.credentials.password
            )
            for cluster in clusters
        }
    )
