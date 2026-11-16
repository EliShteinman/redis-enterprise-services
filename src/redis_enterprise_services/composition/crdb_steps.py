from redis_enterprise_services.cluster.cluster_target_resolver import ClusterTargetResolver
from redis_enterprise_services.composition.cluster_waiters import ClusterWaiters
from redis_enterprise_services.config.crdb_settings import CrdbSettings
from redis_enterprise_services.config.database_settings import DatabaseSettings
from redis_enterprise_services.crdbs.rest_crdb_repository import RestCrdbRepository
from redis_enterprise_services.steps.create_crdb import CreateCrdbStep
from redis_enterprise_services.steps.find_local_crdb_instance import FindLocalCrdbInstanceStep
from redis_enterprise_services.steps.read_crdb import ReadCrdbStep
from redis_enterprise_services.steps.update_crdb_instances import UpdateCrdbInstancesStep


class CrdbSteps:
    def __init__(
        self,
        *,
        create_crdb: CreateCrdbStep,
        find_local_crdb_instance: FindLocalCrdbInstanceStep,
        update_crdb_instances: UpdateCrdbInstancesStep,
        read_crdb: ReadCrdbStep,
    ) -> None:
        self.create_crdb: CreateCrdbStep = create_crdb
        self.find_local_crdb_instance: FindLocalCrdbInstanceStep = find_local_crdb_instance
        self.update_crdb_instances: UpdateCrdbInstancesStep = update_crdb_instances
        self.read_crdb: ReadCrdbStep = read_crdb


def build_crdb_steps(
    *,
    crdb: CrdbSettings,
    database: DatabaseSettings,
    repository: RestCrdbRepository,
    waiters: ClusterWaiters,
    target_resolver: ClusterTargetResolver,
) -> CrdbSteps:
    return CrdbSteps(
        create_crdb=CreateCrdbStep(
            repository=repository,
            task_tracker=waiters.crdb_task_tracker,
            target_resolver=target_resolver,
            guid_field=crdb.task.guid_field,
        ),
        find_local_crdb_instance=FindLocalCrdbInstanceStep(
            repository=repository, activation_waiter=waiters.database, target_resolver=target_resolver
        ),
        update_crdb_instances=UpdateCrdbInstancesStep(
            repository=repository,
            task_tracker=waiters.crdb_task_tracker,
            target_resolver=target_resolver,
            order_insensitive_fields=database.order_insensitive_fields,
            fields_defaulting_to_empty_list=database.fields_defaulting_to_empty_list,
        ),
        read_crdb=ReadCrdbStep(
            repository=repository,
            target_resolver=target_resolver,
            secret_fields=frozenset(database.secret_fields),
            order_insensitive_fields=database.order_insensitive_fields,
            cluster_added_item_fields=crdb.cluster_added_item_fields,
        ),
    )
