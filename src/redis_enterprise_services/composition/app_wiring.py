from redis import Redis

from redis_enterprise_services.background.periodic_thread import PeriodicThread
from redis_enterprise_services.background.thread_pool_task_runner import ThreadPoolTaskRunner
from redis_enterprise_services.composition.cluster_wiring import ClusterWiring
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
from redis_enterprise_services.planning.availability.creation_naming import CreationNaming
from redis_enterprise_services.planning.availability.listed_name_lookup import ListedNameLookup
from redis_enterprise_services.planning.availability.name_availability import NameAvailability
from redis_enterprise_services.planning.availability.name_lookups_by_kind import NameLookupsByKind
from redis_enterprise_services.planning.cluster_directory import ClusterDirectory
from redis_enterprise_services.planning.database_defaults import database_defaults_from
from redis_enterprise_services.planning.naming.configured_name_rules import configured_name_rules
from redis_enterprise_services.planning.naming.name_validator import NameValidator
from redis_enterprise_services.planning.single_candidate_chooser import SingleCandidateChooser
from redis_enterprise_services.planning.single_site_creation_planner import SingleSiteCreationPlanner
from redis_enterprise_services.planning.site_cluster_resolver import SiteClusterResolver
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
from redis_enterprise_services.recovery.abandoned_sweep import AbandonedSweep
from redis_enterprise_services.saga.engine.compensator import Compensator
from redis_enterprise_services.saga.engine.saga_executor import SagaExecutor
from redis_enterprise_services.saga.engine.step_runner import StepRunner
from redis_enterprise_services.state.redis_abandoned_store import RedisAbandonedStore
from redis_enterprise_services.state.redis_client import build_redis_client
from redis_enterprise_services.state.redis_heartbeat_store import RedisHeartbeatStore
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.state.redis_operation_store import RedisOperationStore
from redis_enterprise_services.state.redis_saga_lock import RedisSagaLock
from redis_enterprise_services.state.redis_saga_record_store import RedisSagaRecordStore
from redis_enterprise_services.state.tracked_record_writer import TrackedRecordWriter
from redis_enterprise_services.steps.failure_classifier import ClusterFailureClassifier
from redis_enterprise_services.timing.clock import MonotonicClock
from redis_enterprise_services.timing.deadline_polling import DeadlinePolling
from redis_enterprise_services.timing.sleeper import Sleeper, SystemSleeper


class AppWiring:
    def __init__(self, *, settings: Settings) -> None:
        sleeper: SystemSleeper = SystemSleeper()
        deadline_polling: DeadlinePolling = DeadlinePolling(clock=MonotonicClock(), sleeper=sleeper)
        redis_client: Redis = build_redis_client(settings=settings.state)
        redis_keys: RedisKeys = RedisKeys(
            key_prefix=settings.state.key_prefix, hash_tag=settings.state.hash_tag
        )
        record_writer: TrackedRecordWriter = TrackedRecordWriter(client=redis_client)
        self.operation_store: OperationStore = RedisOperationStore(
            client=redis_client,
            keys=redis_keys,
            record_writer=record_writer,
            finished_ttl_seconds=settings.state.finished_ttl_seconds,
            heartbeat_ttl_seconds=settings.liveness.heartbeat_ttl_seconds,
        )
        self.task_runner: ThreadPoolTaskRunner = ThreadPoolTaskRunner(settings=settings.background)
        operation_heartbeats: InProcessOperationHeartbeats = InProcessOperationHeartbeats(
            heartbeat_store=RedisHeartbeatStore(
                client=redis_client,
                keys=redis_keys,
                heartbeat_ttl_seconds=settings.liveness.heartbeat_ttl_seconds,
            )
        )
        self.operation_heartbeat_thread: PeriodicThread = PeriodicThread(
            name="operation heartbeat",
            interval_seconds=settings.liveness.heartbeat_interval_seconds,
            task=operation_heartbeats.mark_tracked_alive,
        )
        cluster_wiring: ClusterWiring = ClusterWiring(settings=settings, deadline_polling=deadline_polling)
        user_resource_naming: UserResourceNaming = UserResourceNaming(settings=settings.user_resources)
        public_errors: PublicErrors = PublicErrors(
            settings=settings.operation, internal_error_message=settings.api.internal_error_message
        )
        saga_lock: RedisSagaLock = RedisSagaLock(
            client=redis_client,
            keys=redis_keys,
            settings=settings.state.lock,
            deadline_polling=deadline_polling,
        )
        saga_record_store: RedisSagaRecordStore = RedisSagaRecordStore(
            client=redis_client,
            keys=redis_keys,
            record_writer=record_writer,
            finished_ttl_seconds=settings.state.finished_ttl_seconds,
        )
        self.abandoned_sweep_thread: PeriodicThread = PeriodicThread(
            name="abandoned operations sweep",
            interval_seconds=settings.liveness.abandoned_sweep_interval_seconds,
            task=AbandonedSweep(
                store=RedisAbandonedStore(
                    client=redis_client,
                    keys=redis_keys,
                    finished_ttl_seconds=settings.state.finished_ttl_seconds,
                ),
                public_errors=public_errors,
            ).sweep,
        )
        self.database_creation: DatabaseCreation = DatabaseCreation(
            preparation=CreationPreparation(
                name_validator=NameValidator(rules=configured_name_rules(settings=settings.naming.database)),
                site_cluster_resolver=SiteClusterResolver(
                    directory=ClusterDirectory(clusters=settings.clusters), chooser=SingleCandidateChooser()
                ),
                database_defaults=database_defaults_from(settings=settings.database_defaults),
            ),
            execution=CreationExecution(
                name_check_scope=ChosenClusterScope(),
                name_availability=NameAvailability(
                    lookups=NameLookupsByKind(
                        database=ListedNameLookup(lister=cluster_wiring.database_repository),
                        acl=ListedNameLookup(lister=cluster_wiring.acl_repository),
                        role=ListedNameLookup(lister=cluster_wiring.role_repository),
                        user=ListedNameLookup(lister=cluster_wiring.user_repository),
                    ),
                    target_resolver=cluster_wiring.target_resolver,
                ),
                creation_naming=CreationNaming(resource_naming=user_resource_naming),
                planner=SingleSiteCreationPlanner(
                    role_management=settings.user_resources.role_management,
                    cluster_fields=settings.cluster_api.fields,
                    resource_naming=user_resource_naming,
                    create_database_step=cluster_wiring.create_database_step,
                    create_acl_step=cluster_wiring.create_acl_step,
                    create_role_step=cluster_wiring.create_role_step,
                    create_user_step=cluster_wiring.create_user_step,
                    update_database_step=cluster_wiring.update_database_step,
                ),
                saga_executor=build_saga_executor(
                    settings=settings,
                    saga_lock=saga_lock,
                    saga_record_store=saga_record_store,
                    sleeper=sleeper,
                ),
                outcome_translator=CreationOutcomeTranslator(
                    resource_naming=user_resource_naming, public_errors=public_errors
                ),
                public_errors=public_errors,
                saga_record_reader=saga_record_store,
                operation_store=self.operation_store,
            ),
            operation_starter=OperationStarter(
                store=self.operation_store,
                task_runner=self.task_runner,
                operation_heartbeats=operation_heartbeats,
                public_errors=public_errors,
            ),
        )


def build_saga_executor(
    *, settings: Settings, saga_lock: RedisSagaLock, saga_record_store: RedisSagaRecordStore, sleeper: Sleeper
) -> SagaExecutor:
    failure_classifier: ClusterFailureClassifier = ClusterFailureClassifier(
        transient_error_codes=settings.cluster_api.transient_error_codes
    )
    return SagaExecutor(
        record_writer=saga_record_store,
        lock=saga_lock,
        runner=StepRunner(settings=settings.saga, classifier=failure_classifier, sleeper=sleeper),
        compensator=Compensator(settings=settings.saga, classifier=failure_classifier, sleeper=sleeper),
    )
