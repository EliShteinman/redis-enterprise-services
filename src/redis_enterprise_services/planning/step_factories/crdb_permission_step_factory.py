from functools import partial

from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.planning.crdb_task_ids import crdb_task_id
from redis_enterprise_services.planning.creation_step_keys import PERMISSIONS_STEP_KEY
from redis_enterprise_services.planning.step_factories.crdb_step_factory import (
    created_crdb_of,
    local_instance_of,
)
from redis_enterprise_services.planning.step_factories.role_permission_values import RolePermissionValues
from redis_enterprise_services.planning.user_resources import UserResources
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.plan.planned_step import PlannedStep
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep
from redis_enterprise_services.saga.plan.step_results import StepResults
from redis_enterprise_services.steps.update_crdb_instances import (
    CrdbInstancesSnapshot,
    UpdateCrdbInstancesInput,
)


class CrdbPermissionStepFactory:
    def __init__(
        self,
        *,
        update_instances_step: SagaStep[UpdateCrdbInstancesInput, CrdbInstancesSnapshot],
        permission_values: RolePermissionValues,
    ) -> None:
        self._update_instances_step: SagaStep[UpdateCrdbInstancesInput, CrdbInstancesSnapshot] = (
            update_instances_step
        )
        self._permission_values: RolePermissionValues = permission_values

    def steps(
        self,
        *,
        saga_id: str,
        coordinator: ClusterAddress,
        resources_of_users_by_fqdn: dict[str, list[UserResources]],
    ) -> list[PreparableStep]:
        if not any(resources_of_users_by_fqdn.values()):
            return []
        return [
            PlannedStep(
                key=PERMISSIONS_STEP_KEY,
                step=self._update_instances_step,
                build_input=partial(
                    self._permissions_input,
                    coordinator=coordinator,
                    resources_of_users_by_fqdn=resources_of_users_by_fqdn,
                    task_id=crdb_task_id(saga_id=saga_id, step_key=PERMISSIONS_STEP_KEY),
                ),
            )
        ]

    def _permissions_input(
        self,
        *,
        step_results: StepResults,
        coordinator: ClusterAddress,
        resources_of_users_by_fqdn: dict[str, list[UserResources]],
        task_id: str,
    ) -> UpdateCrdbInstancesInput:
        return UpdateCrdbInstancesInput(
            coordinator=coordinator,
            guid=created_crdb_of(step_results=step_results).guid,
            values_by_instance={
                local_instance_of(
                    step_results=step_results, cluster_fqdn=cluster_fqdn
                ).instance_id: self._permission_values.of_users(
                    step_results=step_results, resources_of_users=resources_of_users
                )
                for cluster_fqdn, resources_of_users in resources_of_users_by_fqdn.items()
            },
            task_id=task_id,
        )
