import logging

from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.planning.cluster_address import address_of
from redis_enterprise_services.planning.creation_lock_keys import creation_lock_keys
from redis_enterprise_services.planning.creation_step_keys import READ_DATABASE_STEP_KEY
from redis_enterprise_services.planning.database_spec import DatabaseSpec
from redis_enterprise_services.planning.step_factories.database_permission_step_factory import (
    DatabasePermissionStepFactory,
)
from redis_enterprise_services.planning.step_factories.database_step_factory import (
    DatabaseStepFactory,
    created_database_uid,
)
from redis_enterprise_services.planning.step_factories.read_database_step_factory import (
    ReadDatabaseStepFactory,
)
from redis_enterprise_services.planning.step_factories.user_resource_step_factory import (
    UserResourceStepFactory,
)
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
from redis_enterprise_services.planning.user_resources import UserResources, user_resources
from redis_enterprise_services.saga.plan.saga_plan import SagaPlan
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep

logger: logging.Logger = logging.getLogger(name=__name__)


class SingleSiteCreationPlanner:
    def __init__(
        self,
        *,
        resource_naming: UserResourceNaming,
        database_steps: DatabaseStepFactory,
        user_resource_steps: UserResourceStepFactory,
        permission_steps: DatabasePermissionStepFactory,
        read_database_steps: ReadDatabaseStepFactory,
    ) -> None:
        self._resource_naming: UserResourceNaming = resource_naming
        self._database_steps: DatabaseStepFactory = database_steps
        self._user_resource_steps: UserResourceStepFactory = user_resource_steps
        self._permission_steps: DatabasePermissionStepFactory = permission_steps
        self._read_database_steps: ReadDatabaseStepFactory = read_database_steps

    def plan(self, *, cluster: ConfiguredCluster, spec: DatabaseSpec) -> SagaPlan:
        steps: list[PreparableStep] = self._steps(address=address_of(cluster=cluster), spec=spec)
        logger.info(msg=f"database {spec.database.name} on {cluster.fqdn} plans {len(steps)} steps")
        return SagaPlan(steps=steps, lock_keys=creation_lock_keys(clusters=[cluster], spec=spec))

    def _steps(self, *, address: ClusterAddress, spec: DatabaseSpec) -> list[PreparableStep]:
        resources_of_users: list[UserResources] = [
            user_resources(naming=self._resource_naming, database_name=spec.database.name, user=user)
            for user in spec.users
        ]
        return [
            self._database_steps.creation_step(address=address, database=spec.database),
            *(
                step
                for user, resources in zip(spec.users, resources_of_users, strict=True)
                for step in self._user_resource_steps.steps_for_user(
                    address=address, user=user, resources=resources, database_uid=created_database_uid
                )
            ),
            *self._permission_steps.steps(
                address=address, database_uid=created_database_uid, resources_of_users=resources_of_users
            ),
            self._read_database_steps.step(
                key=READ_DATABASE_STEP_KEY,
                address=address,
                database_uid=created_database_uid,
                resources_of_users=resources_of_users,
            ),
        ]
