from redis_enterprise_services.composition.background_wiring import BackgroundWiring
from redis_enterprise_services.composition.cluster.cluster_wiring import ClusterWiring
from redis_enterprise_services.composition.creation.creation_execution_builder import CreationExecutionBuilder
from redis_enterprise_services.composition.creation.creation_planner_wiring import (
    build_active_active_planner,
    build_single_site_planner,
)
from redis_enterprise_services.composition.creation.names_check_wiring import build_names_check
from redis_enterprise_services.composition.creation.preparation_wiring import (
    build_database_name_validator,
    build_site_cluster_resolver,
    build_user_names_validator,
    checked_database_defaults,
)
from redis_enterprise_services.composition.state_wiring import StateWiring
from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.service.saga_settings import SagaSettings
from redis_enterprise_services.config.settings import Settings
from redis_enterprise_services.creation.crdb_creation import CrdbCreation
from redis_enterprise_services.creation.database_creation import DatabaseCreation
from redis_enterprise_services.creation.planning.active_active_creation_planning import (
    ActiveActiveCreationPlanning,
)
from redis_enterprise_services.creation.planning.single_site_creation_planning import (
    SingleSiteCreationPlanning,
)
from redis_enterprise_services.creation.preparation.active_active_preparation import ActiveActivePreparation
from redis_enterprise_services.creation.preparation.creation_preparation import CreationPreparation
from redis_enterprise_services.creation.results.active_active_record_reader import ActiveActiveRecordReader
from redis_enterprise_services.creation.results.single_site_record_reader import SingleSiteRecordReader
from redis_enterprise_services.operations.errors.public_errors import PublicErrors
from redis_enterprise_services.operations.operation_starter import OperationStarter
from redis_enterprise_services.planning.availability.creation_names_check import CreationNamesCheck
from redis_enterprise_services.planning.planned.user_resource_naming import UserResourceNaming
from redis_enterprise_services.planning.spec.database_defaults import DatabaseDefaults
from redis_enterprise_services.planning.step_factories.role_permission_values import RolePermissionValues
from redis_enterprise_services.saga.engine.compensator import Compensator
from redis_enterprise_services.saga.engine.saga_executor import SagaExecutor
from redis_enterprise_services.saga.engine.step_runner import StepRunner
from redis_enterprise_services.steps.failure_classifier import ClusterFailureClassifier
from redis_enterprise_services.timing.sleeper import Sleeper


class CreationWiring:
    def __init__(
        self,
        *,
        settings: Settings,
        clusters: list[ConfiguredCluster],
        cluster_wiring: ClusterWiring,
        state_wiring: StateWiring,
        background_wiring: BackgroundWiring,
        public_errors: PublicErrors,
        sleeper: Sleeper,
    ) -> None:
        self._settings: Settings = settings
        self._clusters: list[ConfiguredCluster] = clusters
        self._cluster_wiring: ClusterWiring = cluster_wiring
        self._resource_naming: UserResourceNaming = UserResourceNaming(settings=settings.user_resources)
        self._database_defaults: DatabaseDefaults = checked_database_defaults(
            settings=settings.database_defaults, clusters=clusters
        )
        self._names_check: CreationNamesCheck = build_names_check(
            repositories=cluster_wiring.repositories,
            target_resolver=cluster_wiring.target_resolver,
            resource_naming=self._resource_naming,
        )
        self._permission_values: RolePermissionValues = RolePermissionValues(
            roles_permissions_field=settings.cluster_api.fields.roles_permissions
        )
        self._execution_builder: CreationExecutionBuilder = CreationExecutionBuilder(
            saga_executor=build_saga_executor(
                saga=settings.saga,
                transient_error_codes=settings.cluster_api.transient_error_codes,
                state_wiring=state_wiring,
                sleeper=sleeper,
            ),
            public_errors=public_errors,
            saga_record_reader=state_wiring.saga_record_store,
            operation_store=state_wiring.operation_store,
        )
        self._operation_starter: OperationStarter = build_operation_starter(
            state_wiring=state_wiring, background_wiring=background_wiring, public_errors=public_errors
        )
        self.database_creation: DatabaseCreation = self._database_creation()
        self.crdb_creation: CrdbCreation = self._crdb_creation()

    def _database_creation(self) -> DatabaseCreation:
        return DatabaseCreation(
            preparation=CreationPreparation(
                name_validator=build_database_name_validator(naming=self._settings.naming),
                user_names_validator=build_user_names_validator(
                    redis_names=self._settings.naming.redis, resource_naming=self._resource_naming
                ),
                site_cluster_resolver=build_site_cluster_resolver(clusters=self._clusters),
                database_defaults=self._database_defaults,
            ),
            execution=self._execution_builder.build(
                planning=SingleSiteCreationPlanning(
                    names_check=self._names_check,
                    planner=build_single_site_planner(
                        role_management=self._settings.user_resources.role_management,
                        permission_values=self._permission_values,
                        resource_naming=self._resource_naming,
                        steps=self._cluster_wiring.steps,
                    ),
                ),
                record_reader=SingleSiteRecordReader(
                    resource_naming=self._resource_naming,
                    database_settings=self._settings.database,
                    cluster_fields=self._settings.cluster_api.fields,
                ),
            ),
            operation_starter=self._operation_starter,
        )

    def _crdb_creation(self) -> CrdbCreation:
        return CrdbCreation(
            preparation=ActiveActivePreparation(
                name_validator=build_database_name_validator(naming=self._settings.naming),
                user_names_validator=build_user_names_validator(
                    redis_names=self._settings.naming.redis, resource_naming=self._resource_naming
                ),
                site_cluster_resolver=build_site_cluster_resolver(clusters=self._clusters),
                database_defaults=self._database_defaults,
            ),
            execution=self._execution_builder.build(
                planning=ActiveActiveCreationPlanning(
                    names_check=self._names_check,
                    planner=build_active_active_planner(
                        role_management=self._settings.user_resources.role_management,
                        permission_values=self._permission_values,
                        resource_naming=self._resource_naming,
                        database_defaults=self._database_defaults,
                        database_body_builder=self._cluster_wiring.repositories.database_body_builder,
                        secret_fields=frozenset(self._settings.database.secret_fields),
                        steps=self._cluster_wiring.steps,
                        crdb_steps=self._cluster_wiring.crdb_steps,
                    ),
                ),
                record_reader=ActiveActiveRecordReader(
                    resource_naming=self._resource_naming,
                    database_settings=self._settings.database,
                    cluster_fields=self._settings.cluster_api.fields,
                ),
            ),
            operation_starter=self._operation_starter,
        )


def build_operation_starter(
    *, state_wiring: StateWiring, background_wiring: BackgroundWiring, public_errors: PublicErrors
) -> OperationStarter:
    return OperationStarter(
        store=state_wiring.operation_store,
        task_runner=background_wiring.task_runner,
        operation_heartbeats=background_wiring.operation_heartbeats,
        public_errors=public_errors,
    )


def build_saga_executor(
    *,
    saga: SagaSettings,
    transient_error_codes: frozenset[str],
    state_wiring: StateWiring,
    sleeper: Sleeper,
) -> SagaExecutor:
    failure_classifier: ClusterFailureClassifier = ClusterFailureClassifier(
        transient_error_codes=transient_error_codes
    )
    return SagaExecutor(
        record_writer=state_wiring.saga_record_store,
        lock=state_wiring.saga_lock,
        runner=StepRunner(settings=saga, classifier=failure_classifier, sleeper=sleeper),
        compensator=Compensator(settings=saga, classifier=failure_classifier, sleeper=sleeper),
    )
