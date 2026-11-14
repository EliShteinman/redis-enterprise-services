from redis_enterprise_services.background.periodic_thread import PeriodicThread
from redis_enterprise_services.background.thread_pool_task_runner import ThreadPoolTaskRunner
from redis_enterprise_services.composition.cluster_wiring import ClusterWiring
from redis_enterprise_services.composition.state_wiring import StateWiring
from redis_enterprise_services.config.naming_settings import RedisNameRulesSettings
from redis_enterprise_services.config.settings import Settings
from redis_enterprise_services.creation.creation_execution import CreationExecution
from redis_enterprise_services.creation.creation_outcome_translator import CreationOutcomeTranslator
from redis_enterprise_services.creation.creation_preparation import CreationPreparation
from redis_enterprise_services.creation.database_creation import DatabaseCreation
from redis_enterprise_services.liveness.in_process_operation_heartbeats import InProcessOperationHeartbeats
from redis_enterprise_services.operations.operation_starter import OperationStarter
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.planning.availability.chosen_cluster_scope import ChosenClusterScope
from redis_enterprise_services.planning.availability.creation_names_check import CreationNamesCheck
from redis_enterprise_services.planning.availability.creation_naming import CreationNaming
from redis_enterprise_services.planning.availability.listed_name_lookup import ListedNameLookup
from redis_enterprise_services.planning.availability.name_availability import NameAvailability
from redis_enterprise_services.planning.availability.name_lookups_by_kind import NameLookupsByKind
from redis_enterprise_services.planning.cluster_directory import ClusterDirectory
from redis_enterprise_services.planning.database_defaults import database_defaults_from
from redis_enterprise_services.planning.naming.configured_name_rules import configured_name_rules
from redis_enterprise_services.planning.naming.name_validator import NameValidator
from redis_enterprise_services.planning.naming.user_names_validator import UserNamesValidator
from redis_enterprise_services.planning.single_candidate_chooser import SingleCandidateChooser
from redis_enterprise_services.planning.single_site_creation_planner import SingleSiteCreationPlanner
from redis_enterprise_services.planning.site_cluster_resolver import SiteClusterResolver
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
from redis_enterprise_services.recovery.abandoned_sweep import AbandonedSweep
from redis_enterprise_services.saga.contract.saga_lock import SagaLock
from redis_enterprise_services.saga.contract.saga_record_store import SagaRecordWriter
from redis_enterprise_services.saga.engine.compensator import Compensator
from redis_enterprise_services.saga.engine.saga_executor import SagaExecutor
from redis_enterprise_services.saga.engine.step_runner import StepRunner
from redis_enterprise_services.steps.failure_classifier import ClusterFailureClassifier
from redis_enterprise_services.timing.clock import MonotonicClock
from redis_enterprise_services.timing.deadline_polling import DeadlinePolling
from redis_enterprise_services.timing.sleeper import Sleeper, SystemSleeper

OPERATION_HEARTBEAT_THREAD_NAME: str = "operation heartbeat"
ABANDONED_SWEEP_THREAD_NAME: str = "abandoned operations sweep"


class AppWiring:
    def __init__(self, *, settings: Settings) -> None:
        sleeper: SystemSleeper = SystemSleeper()
        deadline_polling: DeadlinePolling = DeadlinePolling(clock=MonotonicClock(), sleeper=sleeper)
        state_wiring: StateWiring = StateWiring(settings=settings, deadline_polling=deadline_polling)
        task_runner: ThreadPoolTaskRunner = ThreadPoolTaskRunner(settings=settings.background)
        operation_heartbeats: InProcessOperationHeartbeats = InProcessOperationHeartbeats(
            heartbeat_store=state_wiring.heartbeat_store
        )
        public_errors: PublicErrors = build_public_errors(settings=settings)
        self.public_errors: PublicErrors = public_errors
        self.operation_store: OperationStore = state_wiring.operation_store
        self.database_creation: DatabaseCreation = build_database_creation(
            settings=settings,
            state_wiring=state_wiring,
            cluster_wiring=ClusterWiring(settings=settings, deadline_polling=deadline_polling),
            operation_starter=build_operation_starter(
                state_wiring=state_wiring,
                task_runner=task_runner,
                operation_heartbeats=operation_heartbeats,
                public_errors=public_errors,
            ),
            public_errors=public_errors,
            sleeper=sleeper,
        )
        self._state_wiring: StateWiring = state_wiring
        self._task_runner: ThreadPoolTaskRunner = task_runner
        self._operation_heartbeat_thread: PeriodicThread = build_operation_heartbeat_thread(
            settings=settings, operation_heartbeats=operation_heartbeats
        )
        self._abandoned_sweep_thread: PeriodicThread = build_abandoned_sweep_thread(
            settings=settings, state_wiring=state_wiring, public_errors=public_errors
        )

    def start(self) -> None:
        self._operation_heartbeat_thread.start()
        self._abandoned_sweep_thread.start()

    def stop(self) -> None:
        self._abandoned_sweep_thread.stop()
        self._task_runner.close()
        self._operation_heartbeat_thread.stop()
        self._state_wiring.close()


def build_public_errors(*, settings: Settings) -> PublicErrors:
    return PublicErrors(
        settings=settings.operation,
        internal_error_message=settings.api.internal_error_message,
        unexpected_error_message=settings.api.unexpected_error_message,
    )


def build_operation_starter(
    *,
    state_wiring: StateWiring,
    task_runner: ThreadPoolTaskRunner,
    operation_heartbeats: InProcessOperationHeartbeats,
    public_errors: PublicErrors,
) -> OperationStarter:
    return OperationStarter(
        store=state_wiring.operation_store,
        task_runner=task_runner,
        operation_heartbeats=operation_heartbeats,
        public_errors=public_errors,
    )


def build_operation_heartbeat_thread(
    *, settings: Settings, operation_heartbeats: InProcessOperationHeartbeats
) -> PeriodicThread:
    return PeriodicThread(
        name=OPERATION_HEARTBEAT_THREAD_NAME,
        interval_seconds=settings.liveness.heartbeat_interval_seconds,
        task=operation_heartbeats.mark_tracked_alive,
    )


def build_abandoned_sweep_thread(
    *, settings: Settings, state_wiring: StateWiring, public_errors: PublicErrors
) -> PeriodicThread:
    return PeriodicThread(
        name=ABANDONED_SWEEP_THREAD_NAME,
        interval_seconds=settings.liveness.abandoned_sweep_interval_seconds,
        task=AbandonedSweep(store=state_wiring.abandoned_store, public_errors=public_errors).sweep,
    )


def build_database_creation(
    *,
    settings: Settings,
    state_wiring: StateWiring,
    cluster_wiring: ClusterWiring,
    operation_starter: OperationStarter,
    public_errors: PublicErrors,
    sleeper: Sleeper,
) -> DatabaseCreation:
    user_resource_naming: UserResourceNaming = UserResourceNaming(settings=settings.user_resources)
    return DatabaseCreation(
        preparation=build_creation_preparation(settings=settings, resource_naming=user_resource_naming),
        execution=CreationExecution(
            names_check=build_names_check(
                cluster_wiring=cluster_wiring, user_resource_naming=user_resource_naming
            ),
            planner=build_planner(
                settings=settings, cluster_wiring=cluster_wiring, user_resource_naming=user_resource_naming
            ),
            saga_executor=build_saga_executor(
                settings=settings,
                saga_lock=state_wiring.saga_lock,
                saga_record_writer=state_wiring.saga_record_store,
                sleeper=sleeper,
            ),
            outcome_translator=CreationOutcomeTranslator(
                resource_naming=user_resource_naming,
                public_errors=public_errors,
                database_settings=settings.database,
            ),
            public_errors=public_errors,
            saga_record_reader=state_wiring.saga_record_store,
            operation_store=state_wiring.operation_store,
        ),
        operation_starter=operation_starter,
    )


def build_creation_preparation(
    *, settings: Settings, resource_naming: UserResourceNaming
) -> CreationPreparation:
    redis_names: RedisNameRulesSettings = settings.naming.redis
    return CreationPreparation(
        name_validator=NameValidator(
            rules=[
                *configured_name_rules(settings=redis_names.database),
                *configured_name_rules(settings=settings.naming.database),
            ]
        ),
        user_names_validator=UserNamesValidator(
            user_name_validator=NameValidator(rules=configured_name_rules(settings=redis_names.user)),
            acl_and_role_name_validator=NameValidator(
                rules=configured_name_rules(settings=redis_names.acl_and_role)
            ),
            resource_naming=resource_naming,
        ),
        site_cluster_resolver=SiteClusterResolver(
            directory=ClusterDirectory(clusters=settings.clusters), chooser=SingleCandidateChooser()
        ),
        database_defaults=database_defaults_from(
            settings=settings.database_defaults, clusters=settings.clusters
        ),
    )


def build_names_check(
    *, cluster_wiring: ClusterWiring, user_resource_naming: UserResourceNaming
) -> CreationNamesCheck:
    return CreationNamesCheck(
        name_check_scope=ChosenClusterScope(),
        name_availability=NameAvailability(
            lookups=NameLookupsByKind(
                database=ListedNameLookup(lister=cluster_wiring.repositories.database),
                acl=ListedNameLookup(lister=cluster_wiring.repositories.acl),
                role=ListedNameLookup(lister=cluster_wiring.repositories.role),
                user=ListedNameLookup(lister=cluster_wiring.repositories.user),
            ),
            target_resolver=cluster_wiring.target_resolver,
        ),
        creation_naming=CreationNaming(resource_naming=user_resource_naming),
    )


def build_planner(
    *, settings: Settings, cluster_wiring: ClusterWiring, user_resource_naming: UserResourceNaming
) -> SingleSiteCreationPlanner:
    return SingleSiteCreationPlanner(
        role_management=settings.user_resources.role_management,
        cluster_fields=settings.cluster_api.fields,
        resource_naming=user_resource_naming,
        create_database_step=cluster_wiring.steps.create_database,
        create_acl_step=cluster_wiring.steps.create_acl,
        create_role_step=cluster_wiring.steps.create_role,
        create_user_step=cluster_wiring.steps.create_user,
        update_database_step=cluster_wiring.steps.update_database,
        read_database_step=cluster_wiring.steps.read_database,
    )


def build_saga_executor(
    *, settings: Settings, saga_lock: SagaLock, saga_record_writer: SagaRecordWriter, sleeper: Sleeper
) -> SagaExecutor:
    failure_classifier: ClusterFailureClassifier = ClusterFailureClassifier(
        transient_error_codes=settings.cluster_api.transient_error_codes
    )
    return SagaExecutor(
        record_writer=saga_record_writer,
        lock=saga_lock,
        runner=StepRunner(settings=settings.saga, classifier=failure_classifier, sleeper=sleeper),
        compensator=Compensator(settings=settings.saga, classifier=failure_classifier, sleeper=sleeper),
    )
