import logging
from functools import partial

from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.redis_api.crdb_settings import CrdbCreationSettings
from redis_enterprise_services.planning.active_active_planned_resources import site_user_resources
from redis_enterprise_services.planning.active_active_spec import ActiveActiveSpec
from redis_enterprise_services.planning.crdb_coordinator import coordinator_of
from redis_enterprise_services.planning.keys.creation_lock_keys import creation_lock_keys
from redis_enterprise_services.planning.keys.creation_step_keys import READ_DATABASE_STEP_KEY, on_site
from redis_enterprise_services.planning.placement.cluster_address import address_of
from redis_enterprise_services.planning.planned.user_resource_naming import UserResourceNaming
from redis_enterprise_services.planning.planned.user_resources import UserResources
from redis_enterprise_services.planning.spec.database_defaults import DatabaseDefaults
from redis_enterprise_services.planning.spec.database_spec import DatabaseUserSpec
from redis_enterprise_services.planning.step_factories.crdb_permission_step_factory import (
    CrdbPermissionStepFactory,
)
from redis_enterprise_services.planning.step_factories.crdb_step_factory import (
    CrdbStepFactory,
    local_database_uid,
)
from redis_enterprise_services.planning.step_factories.read_crdb_step_factory import ReadCrdbStepFactory
from redis_enterprise_services.planning.step_factories.read_database_step_factory import (
    ReadDatabaseStepFactory,
)
from redis_enterprise_services.planning.step_factories.user_resource_step_factory import (
    UserResourceStepFactory,
)
from redis_enterprise_services.saga.plan.saga_plan import SagaPlan
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep

logger: logging.Logger = logging.getLogger(name=__name__)


class ActiveActiveCreationPlanner:
    def __init__(
        self,
        *,
        resource_naming: UserResourceNaming,
        database_defaults: DatabaseDefaults,
        crdb_steps: CrdbStepFactory,
        user_resource_steps: UserResourceStepFactory,
        permission_steps: CrdbPermissionStepFactory,
        read_database_steps: ReadDatabaseStepFactory,
        read_crdb_steps: ReadCrdbStepFactory,
    ) -> None:
        self._resource_naming: UserResourceNaming = resource_naming
        self._database_defaults: DatabaseDefaults = database_defaults
        self._crdb_steps: CrdbStepFactory = crdb_steps
        self._user_resource_steps: UserResourceStepFactory = user_resource_steps
        self._permission_steps: CrdbPermissionStepFactory = permission_steps
        self._read_database_steps: ReadDatabaseStepFactory = read_database_steps
        self._read_crdb_steps: ReadCrdbStepFactory = read_crdb_steps

    def plan(self, *, saga_id: str, clusters: list[ConfiguredCluster], spec: ActiveActiveSpec) -> SagaPlan:
        steps: list[PreparableStep] = self._steps(saga_id=saga_id, clusters=clusters, spec=spec)
        logger.info(
            msg=f"Active-Active database {spec.database.name} on {[cluster.fqdn for cluster in clusters]} "
            f"plans {len(steps)} steps"
        )
        return SagaPlan(steps=steps, lock_keys=creation_lock_keys(clusters=clusters, spec=spec))

    def _steps(
        self, *, saga_id: str, clusters: list[ConfiguredCluster], spec: ActiveActiveSpec
    ) -> list[PreparableStep]:
        coordinator: ClusterAddress = address_of(cluster=coordinator_of(clusters=clusters))
        settings: CrdbCreationSettings = self._database_defaults.crdb_settings(
            cluster=coordinator_of(clusters=clusters), requested=spec.crdb
        )
        resources_of_users_by_fqdn: dict[str, list[UserResources]] = {
            cluster.fqdn: self._resources_of_users_on(cluster=cluster, spec=spec) for cluster in clusters
        }
        return [
            self._crdb_steps.creation_step(
                saga_id=saga_id,
                coordinator=coordinator,
                members=[address_of(cluster=cluster) for cluster in clusters],
                database=spec.database,
                settings=settings,
            ),
            *(self._crdb_steps.local_instance_step(cluster=cluster) for cluster in clusters),
            *(
                step
                for cluster in clusters
                for step in self._user_steps_on(
                    cluster=cluster,
                    users=spec.users,
                    resources_of_users=resources_of_users_by_fqdn[cluster.fqdn],
                )
            ),
            *self._permission_steps.steps(
                saga_id=saga_id,
                coordinator=coordinator,
                resources_of_users_by_fqdn=resources_of_users_by_fqdn,
            ),
            *(
                self._read_database_step_on(
                    cluster=cluster, resources_of_users=resources_of_users_by_fqdn[cluster.fqdn]
                )
                for cluster in clusters
            ),
            self._read_crdb_steps.step(coordinator=coordinator, database=spec.database, settings=settings),
        ]

    def _resources_of_users_on(
        self, *, cluster: ConfiguredCluster, spec: ActiveActiveSpec
    ) -> list[UserResources]:
        return [
            site_user_resources(
                naming=self._resource_naming,
                database_name=spec.database.name,
                user=user,
                cluster_fqdn=cluster.fqdn,
            )
            for user in spec.users
        ]

    def _user_steps_on(
        self,
        *,
        cluster: ConfiguredCluster,
        users: list[DatabaseUserSpec],
        resources_of_users: list[UserResources],
    ) -> list[PreparableStep]:
        return [
            step
            for user, resources in zip(users, resources_of_users, strict=True)
            for step in self._user_resource_steps.steps_for_user(
                address=address_of(cluster=cluster),
                user=user,
                resources=resources,
                database_uid=partial(local_database_uid, cluster_fqdn=cluster.fqdn),
            )
        ]

    def _read_database_step_on(
        self, *, cluster: ConfiguredCluster, resources_of_users: list[UserResources]
    ) -> PreparableStep:
        return self._read_database_steps.step(
            key=on_site(cluster_fqdn=cluster.fqdn, step_key=READ_DATABASE_STEP_KEY),
            address=address_of(cluster=cluster),
            database_uid=partial(local_database_uid, cluster_fqdn=cluster.fqdn),
            resources_of_users=resources_of_users,
        )
