import logging
from functools import partial

from pydantic import JsonValue

from redis_enterprise_services.acls.models import NewAcl
from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.config.cluster_api_settings import ClusterFieldSettings
from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.crdb_settings import CrdbCreationSettings
from redis_enterprise_services.config.role_management import RoleManagement
from redis_enterprise_services.databases.models import DatabaseFieldsSnapshot
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.planning.active_active_planned_resources import site_user_resources
from redis_enterprise_services.planning.cluster_address import address_of
from redis_enterprise_services.planning.crdb_coordinator import coordinator_of
from redis_enterprise_services.planning.crdb_task_ids import crdb_task_id
from redis_enterprise_services.planning.creation_inputs import (
    creation_lock_keys,
    fixed_input,
    fixed_resource_input,
    role_permissions,
    user_input,
)
from redis_enterprise_services.planning.creation_step_keys import (
    CRDB_STEP_KEY,
    LOCAL_DATABASE_STEP_KEY,
    PERMISSIONS_STEP_KEY,
    READ_CRDB_STEP_KEY,
    READ_DATABASE_STEP_KEY,
    on_site,
)
from redis_enterprise_services.planning.database_defaults import DatabaseDefaults
from redis_enterprise_services.planning.database_spec import DatabaseSpec, DatabaseUserSpec
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
from redis_enterprise_services.planning.user_resources import UserResources
from redis_enterprise_services.resources.cluster_object_body import without_fields
from redis_enterprise_services.resources.creation_body_builder import CreationBodyBuilder
from redis_enterprise_services.resources.models import CreatedResource, CreateResourceInput
from redis_enterprise_services.roles.models import NewRole
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.plan.planned_step import PlannedStep
from redis_enterprise_services.saga.plan.saga_plan import SagaPlan
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep
from redis_enterprise_services.saga.plan.step_results import StepResults
from redis_enterprise_services.steps.create_crdb import CreateCrdbInput, CreatedCrdb
from redis_enterprise_services.steps.find_local_crdb_instance import (
    FindLocalCrdbInstanceInput,
    LocalCrdbInstance,
)
from redis_enterprise_services.steps.read_crdb import CrdbConfigSnapshot, ReadCrdbInput
from redis_enterprise_services.steps.read_database import ReadDatabaseInput
from redis_enterprise_services.steps.update_crdb_instances import (
    CrdbInstancesSnapshot,
    UpdateCrdbInstancesInput,
)
from redis_enterprise_services.users.models import NewUser

logger: logging.Logger = logging.getLogger(name=__name__)


class ActiveActiveCreationPlanner:
    def __init__(
        self,
        *,
        role_management: RoleManagement,
        cluster_fields: ClusterFieldSettings,
        resource_naming: UserResourceNaming,
        database_body_builder: CreationBodyBuilder[NewDatabase],
        secret_fields: frozenset[str],
        database_defaults: DatabaseDefaults,
        create_crdb_step: SagaStep[CreateCrdbInput, CreatedCrdb],
        find_local_instance_step: SagaStep[FindLocalCrdbInstanceInput, LocalCrdbInstance],
        create_acl_step: SagaStep[CreateResourceInput[NewAcl], CreatedResource],
        create_role_step: SagaStep[CreateResourceInput[NewRole], CreatedResource],
        create_user_step: SagaStep[CreateResourceInput[NewUser], CreatedResource],
        update_instances_step: SagaStep[UpdateCrdbInstancesInput, CrdbInstancesSnapshot],
        read_database_step: SagaStep[ReadDatabaseInput, DatabaseFieldsSnapshot],
        read_crdb_step: SagaStep[ReadCrdbInput, CrdbConfigSnapshot],
    ) -> None:
        self._role_management: RoleManagement = role_management
        self._cluster_fields: ClusterFieldSettings = cluster_fields
        self._resource_naming: UserResourceNaming = resource_naming
        self._database_body_builder: CreationBodyBuilder[NewDatabase] = database_body_builder
        self._secret_fields: frozenset[str] = secret_fields
        self._database_defaults: DatabaseDefaults = database_defaults
        self._create_crdb_step: SagaStep[CreateCrdbInput, CreatedCrdb] = create_crdb_step
        self._find_local_instance_step: SagaStep[FindLocalCrdbInstanceInput, LocalCrdbInstance] = (
            find_local_instance_step
        )
        self._create_acl_step: SagaStep[CreateResourceInput[NewAcl], CreatedResource] = create_acl_step
        self._create_role_step: SagaStep[CreateResourceInput[NewRole], CreatedResource] = create_role_step
        self._create_user_step: SagaStep[CreateResourceInput[NewUser], CreatedResource] = create_user_step
        self._update_instances_step: SagaStep[UpdateCrdbInstancesInput, CrdbInstancesSnapshot] = (
            update_instances_step
        )
        self._read_database_step: SagaStep[ReadDatabaseInput, DatabaseFieldsSnapshot] = read_database_step
        self._read_crdb_step: SagaStep[ReadCrdbInput, CrdbConfigSnapshot] = read_crdb_step

    def plan(self, *, saga_id: str, clusters: list[ConfiguredCluster], spec: DatabaseSpec) -> SagaPlan:
        steps: list[PreparableStep] = [
            self._crdb_step(saga_id=saga_id, clusters=clusters, database=spec.database),
            *(self._local_database_step(cluster=cluster) for cluster in clusters),
            *(step for cluster in clusters for step in self._user_steps(cluster=cluster, spec=spec)),
            *self._permissions_steps(saga_id=saga_id, clusters=clusters, spec=spec),
            *(self._read_database_step_on(cluster=cluster, spec=spec) for cluster in clusters),
            self._read_crdb_planned_step(clusters=clusters, database=spec.database),
        ]
        logger.info(
            msg=f"Active-Active database {spec.database.name} on {[cluster.fqdn for cluster in clusters]} "
            f"plans {len(steps)} steps"
        )
        return SagaPlan(
            steps=steps,
            lock_keys=[
                key
                for cluster in clusters
                for key in creation_lock_keys(
                    cluster_url=cluster.api_url,
                    database_name=spec.database.name,
                    user_names=[user.name for user in spec.users],
                )
            ],
        )

    def _crdb_step(
        self, *, saga_id: str, clusters: list[ConfiguredCluster], database: NewDatabase
    ) -> PreparableStep:
        return PlannedStep(
            key=CRDB_STEP_KEY,
            step=self._create_crdb_step,
            build_input=partial(
                fixed_input,
                step_input=CreateCrdbInput(
                    coordinator=address_of(cluster=coordinator_of(clusters=clusters)),
                    members=[address_of(cluster=cluster) for cluster in clusters],
                    database=database,
                    settings=self._database_defaults.crdb_settings(
                        coordinator=coordinator_of(clusters=clusters)
                    ),
                    task_id=crdb_task_id(saga_id=saga_id, step_key=CRDB_STEP_KEY),
                ),
            ),
        )

    def _local_database_step(self, *, cluster: ConfiguredCluster) -> PreparableStep:
        return PlannedStep(
            key=on_site(cluster_fqdn=cluster.fqdn, step_key=LOCAL_DATABASE_STEP_KEY),
            step=self._find_local_instance_step,
            build_input=partial(local_instance_input, address=address_of(cluster=cluster)),
        )

    def _user_steps(self, *, cluster: ConfiguredCluster, spec: DatabaseSpec) -> list[PreparableStep]:
        return [
            step
            for user in spec.users
            for step in self._steps_for_user(
                cluster=cluster,
                user=user,
                resources=site_user_resources(
                    naming=self._resource_naming,
                    database_name=spec.database.name,
                    user=user,
                    cluster_fqdn=cluster.fqdn,
                ),
            )
        ]

    def _steps_for_user(
        self, *, cluster: ConfiguredCluster, user: DatabaseUserSpec, resources: UserResources
    ) -> list[PreparableStep]:
        address: ClusterAddress = address_of(cluster=cluster)
        return [
            PlannedStep(
                key=resources.acl.step_key,
                step=self._create_acl_step,
                build_input=partial(
                    fixed_resource_input,
                    address=address,
                    spec=NewAcl(name=resources.acl.name, acl=user.acl_rule),
                ),
            ),
            PlannedStep(
                key=resources.role.step_key,
                step=self._create_role_step,
                build_input=partial(
                    self._role_input,
                    address=address,
                    role_name=resources.role.name,
                    cluster_fqdn=cluster.fqdn,
                ),
            ),
            PlannedStep(
                key=resources.user.step_key,
                step=self._create_user_step,
                build_input=partial(
                    user_input, address=address, user=user, role_step_key=resources.role.step_key
                ),
            ),
        ]

    def _role_input(
        self, *, step_results: StepResults, address: ClusterAddress, role_name: str, cluster_fqdn: str
    ) -> CreateResourceInput[NewRole]:
        return CreateResourceInput(
            cluster=address,
            spec=NewRole(
                name=role_name,
                management=self._role_management,
                database_uids=[
                    local_instance_of(step_results=step_results, cluster_fqdn=cluster_fqdn).db_uid
                ],
            ),
        )

    def _permissions_steps(
        self, *, saga_id: str, clusters: list[ConfiguredCluster], spec: DatabaseSpec
    ) -> list[PreparableStep]:
        if not spec.users:
            return []
        return [
            PlannedStep(
                key=PERMISSIONS_STEP_KEY,
                step=self._update_instances_step,
                build_input=partial(
                    self._permissions_input,
                    coordinator=address_of(cluster=coordinator_of(clusters=clusters)),
                    clusters=clusters,
                    spec=spec,
                    task_id=crdb_task_id(saga_id=saga_id, step_key=PERMISSIONS_STEP_KEY),
                ),
            )
        ]

    def _permissions_input(
        self,
        *,
        step_results: StepResults,
        coordinator: ClusterAddress,
        clusters: list[ConfiguredCluster],
        spec: DatabaseSpec,
        task_id: str,
    ) -> UpdateCrdbInstancesInput:
        return UpdateCrdbInstancesInput(
            coordinator=coordinator,
            guid=created_crdb_of(step_results=step_results).guid,
            values_by_instance={
                local_instance_of(step_results=step_results, cluster_fqdn=cluster.fqdn).instance_id: (
                    self._permission_values(step_results=step_results, cluster=cluster, spec=spec)
                )
                for cluster in clusters
            },
            task_id=task_id,
        )

    def _read_database_step_on(self, *, cluster: ConfiguredCluster, spec: DatabaseSpec) -> PreparableStep:
        return PlannedStep(
            key=on_site(cluster_fqdn=cluster.fqdn, step_key=READ_DATABASE_STEP_KEY),
            step=self._read_database_step,
            build_input=partial(self._read_database_input, cluster=cluster, spec=spec),
        )

    def _read_database_input(
        self, *, step_results: StepResults, cluster: ConfiguredCluster, spec: DatabaseSpec
    ) -> ReadDatabaseInput:
        return ReadDatabaseInput(
            cluster=address_of(cluster=cluster),
            uid=local_instance_of(step_results=step_results, cluster_fqdn=cluster.fqdn).db_uid,
            expected_values=self._permission_values(step_results=step_results, cluster=cluster, spec=spec)
            if spec.users
            else {},
        )

    def _read_crdb_planned_step(
        self, *, clusters: list[ConfiguredCluster], database: NewDatabase
    ) -> PreparableStep:
        return PlannedStep(
            key=READ_CRDB_STEP_KEY,
            step=self._read_crdb_step,
            build_input=partial(
                read_crdb_input,
                coordinator=address_of(cluster=coordinator_of(clusters=clusters)),
                expected_config=without_fields(
                    fields=self._database_body_builder.creation_body(
                        spec=database, cluster=address_of(cluster=coordinator_of(clusters=clusters))
                    ),
                    names=self._secret_fields,
                ),
                expected_settings=self._database_defaults.crdb_settings(
                    coordinator=coordinator_of(clusters=clusters)
                ),
            ),
        )

    def _permission_values(
        self, *, step_results: StepResults, cluster: ConfiguredCluster, spec: DatabaseSpec
    ) -> dict[str, JsonValue]:
        return {
            self._cluster_fields.roles_permissions: [
                permission.model_dump(mode="json")
                for permission in role_permissions(
                    step_results=step_results,
                    resources_of_users=[
                        site_user_resources(
                            naming=self._resource_naming,
                            database_name=spec.database.name,
                            user=user,
                            cluster_fqdn=cluster.fqdn,
                        )
                        for user in spec.users
                    ],
                )
            ]
        }


def created_crdb_of(*, step_results: StepResults) -> CreatedCrdb:
    return step_results.result_of(key=CRDB_STEP_KEY, result_type=CreatedCrdb)


def local_instance_of(*, step_results: StepResults, cluster_fqdn: str) -> LocalCrdbInstance:
    return step_results.result_of(
        key=on_site(cluster_fqdn=cluster_fqdn, step_key=LOCAL_DATABASE_STEP_KEY),
        result_type=LocalCrdbInstance,
    )


def local_instance_input(*, step_results: StepResults, address: ClusterAddress) -> FindLocalCrdbInstanceInput:
    return FindLocalCrdbInstanceInput(cluster=address, guid=created_crdb_of(step_results=step_results).guid)


def read_crdb_input(
    *,
    step_results: StepResults,
    coordinator: ClusterAddress,
    expected_config: dict[str, JsonValue],
    expected_settings: CrdbCreationSettings,
) -> ReadCrdbInput:
    return ReadCrdbInput(
        coordinator=coordinator,
        guid=created_crdb_of(step_results=step_results).guid,
        expected_config=expected_config,
        expected_settings=expected_settings,
    )
