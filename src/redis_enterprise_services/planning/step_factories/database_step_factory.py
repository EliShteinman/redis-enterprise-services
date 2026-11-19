from functools import partial

from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.planning.keys.creation_step_keys import DATABASE_STEP_KEY
from redis_enterprise_services.planning.step_factories.step_inputs import fixed_input, uid_created_by_step
from redis_enterprise_services.resources.models import CreatedResource, CreateResourceInput
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.plan.planned_step import PlannedStep
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep
from redis_enterprise_services.saga.plan.step_results import StepResults


class DatabaseStepFactory:
    def __init__(
        self, *, create_database_step: SagaStep[CreateResourceInput[NewDatabase], CreatedResource]
    ) -> None:
        self._create_database_step: SagaStep[CreateResourceInput[NewDatabase], CreatedResource] = (
            create_database_step
        )

    def creation_step(self, *, address: ClusterAddress, database: NewDatabase) -> PreparableStep:
        return PlannedStep(
            key=DATABASE_STEP_KEY,
            step=self._create_database_step,
            build_input=partial(fixed_input, step_input=CreateResourceInput(cluster=address, spec=database)),
        )


def created_database_uid(*, step_results: StepResults) -> int:
    return uid_created_by_step(step_results=step_results, step_key=DATABASE_STEP_KEY)
