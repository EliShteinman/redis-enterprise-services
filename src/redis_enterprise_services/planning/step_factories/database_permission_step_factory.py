from functools import partial

from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.databases.models import DatabaseFieldsSnapshot
from redis_enterprise_services.planning.keys.creation_step_keys import PERMISSIONS_STEP_KEY
from redis_enterprise_services.planning.planned.user_resources import UserResources
from redis_enterprise_services.planning.step_factories.role_permission_values import RolePermissionValues
from redis_enterprise_services.planning.step_factories.step_inputs import UidFromStepResults
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.plan.planned_step import PlannedStep
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep
from redis_enterprise_services.saga.plan.step_results import StepResults
from redis_enterprise_services.steps.update_database import UpdateDatabaseInput


class DatabasePermissionStepFactory:
    def __init__(
        self,
        *,
        update_database_step: SagaStep[UpdateDatabaseInput, DatabaseFieldsSnapshot],
        permission_values: RolePermissionValues,
    ) -> None:
        self._update_database_step: SagaStep[UpdateDatabaseInput, DatabaseFieldsSnapshot] = (
            update_database_step
        )
        self._permission_values: RolePermissionValues = permission_values

    def steps(
        self,
        *,
        address: ClusterAddress,
        database_uid: UidFromStepResults,
        resources_of_users: list[UserResources],
    ) -> list[PreparableStep]:
        if not resources_of_users:
            return []
        return [
            PlannedStep(
                key=PERMISSIONS_STEP_KEY,
                step=self._update_database_step,
                build_input=partial(
                    self._permissions_input,
                    address=address,
                    database_uid=database_uid,
                    resources_of_users=resources_of_users,
                ),
            )
        ]

    def _permissions_input(
        self,
        *,
        step_results: StepResults,
        address: ClusterAddress,
        database_uid: UidFromStepResults,
        resources_of_users: list[UserResources],
    ) -> UpdateDatabaseInput:
        return UpdateDatabaseInput(
            cluster=address,
            uid=database_uid(step_results=step_results),
            values=self._permission_values.of_users(
                step_results=step_results, resources_of_users=resources_of_users
            ),
        )
