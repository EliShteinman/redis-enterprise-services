from functools import partial

from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.databases.models import DatabaseFieldsSnapshot
from redis_enterprise_services.planning.planned.user_resources import UserResources
from redis_enterprise_services.planning.step_factories.role_permission_values import RolePermissionValues
from redis_enterprise_services.planning.step_factories.step_inputs import UidFromStepResults
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.plan.planned_step import PlannedStep
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep
from redis_enterprise_services.saga.plan.step_results import StepResults
from redis_enterprise_services.steps.read_database import ReadDatabaseInput


class ReadDatabaseStepFactory:
    def __init__(
        self,
        *,
        read_database_step: SagaStep[ReadDatabaseInput, DatabaseFieldsSnapshot],
        permission_values: RolePermissionValues,
    ) -> None:
        self._read_database_step: SagaStep[ReadDatabaseInput, DatabaseFieldsSnapshot] = read_database_step
        self._permission_values: RolePermissionValues = permission_values

    def step(
        self,
        *,
        key: str,
        address: ClusterAddress,
        database_uid: UidFromStepResults,
        resources_of_users: list[UserResources],
    ) -> PreparableStep:
        return PlannedStep(
            key=key,
            step=self._read_database_step,
            build_input=partial(
                self._read_database_input,
                address=address,
                database_uid=database_uid,
                resources_of_users=resources_of_users,
            ),
        )

    def _read_database_input(
        self,
        *,
        step_results: StepResults,
        address: ClusterAddress,
        database_uid: UidFromStepResults,
        resources_of_users: list[UserResources],
    ) -> ReadDatabaseInput:
        return ReadDatabaseInput(
            cluster=address,
            uid=database_uid(step_results=step_results),
            expected_values=self._permission_values.of_users(
                step_results=step_results, resources_of_users=resources_of_users
            )
            if resources_of_users
            else {},
        )
