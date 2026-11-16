from redis_enterprise_services.cluster.edge_cluster_api_caller import EdgeClusterApiCaller
from redis_enterprise_services.cluster.polling_action_waiter import PollingActionWaiter
from redis_enterprise_services.cluster.read_again_polling import ReadAgainPolling
from redis_enterprise_services.cluster.status_polling import StatusPolling
from redis_enterprise_services.config.action_settings import ActionSettings
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.databases.polling_database_waiter import PollingDatabaseWaiter
from redis_enterprise_services.databases.rest_database_fields_repository import RestDatabaseFieldsRepository
from redis_enterprise_services.resources.action_completion_waiter import ActionCompletionWaiter


class ClusterWaiters:
    def __init__(self, *, database: PollingDatabaseWaiter, action_completion: ActionCompletionWaiter) -> None:
        self.database: PollingDatabaseWaiter = database
        self.action_completion: ActionCompletionWaiter = action_completion


def build_cluster_waiters(
    *,
    database: DatabaseSettings,
    action: ActionSettings,
    status_field: str,
    cluster_api_caller: EdgeClusterApiCaller,
    read_again_polling: ReadAgainPolling,
    database_fields: RestDatabaseFieldsRepository,
) -> ClusterWaiters:
    status_polling: StatusPolling = StatusPolling(
        read_again_polling=read_again_polling, status_field=status_field
    )
    return ClusterWaiters(
        database=PollingDatabaseWaiter(
            fields_reader=database_fields,
            read_again_polling=read_again_polling,
            status_polling=status_polling,
            settings=database,
        ),
        action_completion=ActionCompletionWaiter(
            action_waiter=PollingActionWaiter(
                cluster_api_caller=cluster_api_caller, status_polling=status_polling, settings=action
            )
        ),
    )
