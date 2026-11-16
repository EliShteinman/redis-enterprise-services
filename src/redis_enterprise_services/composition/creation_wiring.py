from redis_enterprise_services.composition.background_wiring import BackgroundWiring
from redis_enterprise_services.composition.cluster_wiring import ClusterWiring
from redis_enterprise_services.composition.planner_wiring import build_single_site_planner
from redis_enterprise_services.composition.planning_wiring import (
    build_database_name_validator,
    build_names_check,
    build_site_cluster_resolver,
    build_user_names_validator,
    checked_database_defaults,
)
from redis_enterprise_services.composition.state_wiring import StateWiring
from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.defaults.database_defaults_settings import DatabaseDefaultsSettings
from redis_enterprise_services.config.defaults.naming_settings import NamingSettings
from redis_enterprise_services.config.service.saga_settings import SagaSettings
from redis_enterprise_services.config.settings import Settings
from redis_enterprise_services.creation.creation_execution import CreationExecution
from redis_enterprise_services.creation.creation_outcome_translator import CreationOutcomeTranslator
from redis_enterprise_services.creation.database_creation import DatabaseCreation
from redis_enterprise_services.creation.preparation.creation_preparation import CreationPreparation
from redis_enterprise_services.operations.errors.public_errors import PublicErrors
from redis_enterprise_services.operations.operation_starter import OperationStarter
from redis_enterprise_services.planning.planned.user_resource_naming import UserResourceNaming
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
        resource_naming: UserResourceNaming = UserResourceNaming(settings=settings.user_resources)
        self.database_creation: DatabaseCreation = DatabaseCreation(
            preparation=build_creation_preparation(
                naming=settings.naming,
                database_defaults=settings.database_defaults,
                resource_naming=resource_naming,
                clusters=clusters,
            ),
            execution=CreationExecution(
                names_check=build_names_check(
                    repositories=cluster_wiring.repositories,
                    target_resolver=cluster_wiring.target_resolver,
                    resource_naming=resource_naming,
                ),
                planner=build_single_site_planner(
                    role_management=settings.user_resources.role_management,
                    permission_values=RolePermissionValues(
                        roles_permissions_field=settings.cluster_api.fields.roles_permissions
                    ),
                    resource_naming=resource_naming,
                    steps=cluster_wiring.steps,
                ),
                saga_executor=build_saga_executor(
                    saga=settings.saga,
                    transient_error_codes=settings.cluster_api.transient_error_codes,
                    state_wiring=state_wiring,
                    sleeper=sleeper,
                ),
                outcome_translator=CreationOutcomeTranslator(
                    resource_naming=resource_naming,
                    public_errors=public_errors,
                    database_settings=settings.database,
                    cluster_fields=settings.cluster_api.fields,
                ),
                public_errors=public_errors,
                saga_record_reader=state_wiring.saga_record_store,
                operation_store=state_wiring.operation_store,
            ),
            operation_starter=build_operation_starter(
                state_wiring=state_wiring, background_wiring=background_wiring, public_errors=public_errors
            ),
        )


def build_creation_preparation(
    *,
    naming: NamingSettings,
    database_defaults: DatabaseDefaultsSettings,
    resource_naming: UserResourceNaming,
    clusters: list[ConfiguredCluster],
) -> CreationPreparation:
    return CreationPreparation(
        name_validator=build_database_name_validator(naming=naming),
        user_names_validator=build_user_names_validator(
            redis_names=naming.redis, resource_naming=resource_naming
        ),
        site_cluster_resolver=build_site_cluster_resolver(clusters=clusters),
        database_defaults=checked_database_defaults(settings=database_defaults, clusters=clusters),
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
