from functools import partial

from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.redis_api.crdb_settings import CrdbCreationSettings
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.planning.crdb_task_ids import crdb_task_id
from redis_enterprise_services.planning.keys.creation_step_keys import (
    CRDB_STEP_KEY,
    LOCAL_DATABASE_STEP_KEY,
    on_site,
)
from redis_enterprise_services.planning.placement.cluster_address import address_of
from redis_enterprise_services.planning.step_factories.step_inputs import fixed_input
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.plan.planned_step import PlannedStep
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep
from redis_enterprise_services.saga.plan.step_results import StepResults
from redis_enterprise_services.steps.crdb.create_crdb import CreateCrdbInput, CreatedCrdb
from redis_enterprise_services.steps.crdb.find_local_crdb_instance import (
    FindLocalCrdbInstanceInput,
    LocalCrdbInstance,
)


class CrdbStepFactory:
    def __init__(
        self,
        *,
        create_crdb_step: SagaStep[CreateCrdbInput, CreatedCrdb],
        find_local_instance_step: SagaStep[FindLocalCrdbInstanceInput, LocalCrdbInstance],
    ) -> None:
        self._create_crdb_step: SagaStep[CreateCrdbInput, CreatedCrdb] = create_crdb_step
        self._find_local_instance_step: SagaStep[FindLocalCrdbInstanceInput, LocalCrdbInstance] = (
            find_local_instance_step
        )

    def creation_step(
        self,
        *,
        saga_id: str,
        coordinator: ClusterAddress,
        members: list[ClusterAddress],
        database: NewDatabase,
        settings: CrdbCreationSettings,
    ) -> PreparableStep:
        return PlannedStep(
            key=CRDB_STEP_KEY,
            step=self._create_crdb_step,
            build_input=partial(
                fixed_input,
                step_input=CreateCrdbInput(
                    coordinator=coordinator,
                    members=members,
                    database=database,
                    settings=settings,
                    task_id=crdb_task_id(saga_id=saga_id, step_key=CRDB_STEP_KEY),
                ),
            ),
        )

    def local_instance_step(self, *, cluster: ConfiguredCluster) -> PreparableStep:
        return PlannedStep(
            key=on_site(cluster_fqdn=cluster.fqdn, step_key=LOCAL_DATABASE_STEP_KEY),
            step=self._find_local_instance_step,
            build_input=partial(local_instance_input, address=address_of(cluster=cluster)),
        )


def created_crdb_of(*, step_results: StepResults) -> CreatedCrdb:
    return step_results.result_of(key=CRDB_STEP_KEY, result_type=CreatedCrdb)


def local_instance_of(*, step_results: StepResults, cluster_fqdn: str) -> LocalCrdbInstance:
    return step_results.result_of(
        key=on_site(cluster_fqdn=cluster_fqdn, step_key=LOCAL_DATABASE_STEP_KEY),
        result_type=LocalCrdbInstance,
    )


def local_database_uid(*, step_results: StepResults, cluster_fqdn: str) -> int:
    return local_instance_of(step_results=step_results, cluster_fqdn=cluster_fqdn).db_uid


def local_instance_input(*, step_results: StepResults, address: ClusterAddress) -> FindLocalCrdbInstanceInput:
    return FindLocalCrdbInstanceInput(cluster=address, guid=created_crdb_of(step_results=step_results).guid)
