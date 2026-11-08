from redis import Redis

from redis_enterprise_services.background.periodic_thread import PeriodicThread
from redis_enterprise_services.background.thread_pool_task_runner import ThreadPoolTaskRunner
from redis_enterprise_services.composition.cluster_wiring import ClusterWiring
from redis_enterprise_services.config.settings import Settings
from redis_enterprise_services.creation.creation_execution import CreationExecution
from redis_enterprise_services.creation.creation_outcome_translator import CreationOutcomeTranslator
from redis_enterprise_services.creation.creation_preparation import CreationPreparation
from redis_enterprise_services.creation.database_creation import DatabaseCreation
from redis_enterprise_services.edge.insecure_warnings import silence_insecure_request_warnings
from redis_enterprise_services.liveness.live_operations import LiveOperations
from redis_enterprise_services.operations.operation_acceptance import OperationAcceptance
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.planning.availability.chosen_cluster_scope import ChosenClusterScope
from redis_enterprise_services.planning.availability.creation_names import CreationNames
from redis_enterprise_services.planning.availability.listed_name_lookup import ListedNameLookup
from redis_enterprise_services.planning.availability.name_availability import NameAvailability
from redis_enterprise_services.planning.availability.name_lookups_by_kind import NameLookupsByKind
from redis_enterprise_services.planning.cluster_directory import ClusterDirectory
from redis_enterprise_services.planning.database_defaults import DatabaseDefaults
from redis_enterprise_services.planning.naming.configured_name_rules import configured_name_rules
from redis_enterprise_services.planning.naming.name_validator import NameValidator
from redis_enterprise_services.planning.single_candidate_chooser import SingleCandidateChooser
from redis_enterprise_services.planning.single_site_creation_planner import SingleSiteCreationPlanner
from redis_enterprise_services.planning.site_cluster_resolver import SiteClusterResolver
from redis_enterprise_services.planning.user_resource_names import UserResourceNames
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
from redis_enterprise_services.steps.failure_classifier import ClusterFailureClassifier
from redis_enterprise_services.timing.clock import MonotonicClock
from redis_enterprise_services.timing.sleeper import SystemSleeper


class AppWiring:
    def __init__(self, *, settings: Settings) -> None:
        silence_insecure_request_warnings()
        redis_client: Redis = build_redis_client(settings=settings.state)
        keys: RedisKeys = RedisKeys(prefix=settings.state.key_prefix, hash_tag=settings.state.hash_tag)
        self.operation_store: OperationStore = RedisOperationStore(
            client=redis_client,
            keys=keys,
            finished_operation_ttl_seconds=settings.state.finished_operation_ttl_seconds,
            heartbeat_ttl_seconds=settings.liveness.heartbeat_ttl_seconds,
        )
        self.task_runner: ThreadPoolTaskRunner = ThreadPoolTaskRunner(settings=settings.background)
        live_operations: LiveOperations = LiveOperations(
            heartbeat_store=RedisHeartbeatStore(
                client=redis_client, keys=keys, heartbeat_ttl_seconds=settings.liveness.heartbeat_ttl_seconds
            )
        )
        self.heartbeat_thread: PeriodicThread = PeriodicThread(
            name="heartbeat",
            interval_seconds=settings.liveness.heartbeat_interval_seconds,
            task=live_operations.refresh_heartbeats,
        )
        cluster_wiring: ClusterWiring = ClusterWiring(settings=settings)
        user_resource_names: UserResourceNames = UserResourceNames(settings=settings.user_resources)
        public_errors: PublicErrors = PublicErrors(
            settings=settings.operation, internal_error_message=settings.api.internal_error_message
        )
        saga_lock: RedisSagaLock = RedisSagaLock(
            client=redis_client,
            keys=keys,
            settings=settings.state.lock,
            sleeper=SystemSleeper(),
            clock=MonotonicClock(),
        )
        saga_record_store: RedisSagaRecordStore = RedisSagaRecordStore(
            client=redis_client,
            keys=keys,
            finished_operation_ttl_seconds=settings.state.finished_operation_ttl_seconds,
        )
        self.abandoned_sweep_thread: PeriodicThread = PeriodicThread(
            name="abandoned operations sweep",
            interval_seconds=settings.liveness.sweep_interval_seconds,
            task=AbandonedSweep(
                store=RedisAbandonedStore(
                    client=redis_client,
                    keys=keys,
                    finished_operation_ttl_seconds=settings.state.finished_operation_ttl_seconds,
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
                database_defaults=DatabaseDefaults(settings=settings.database_defaults),
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
                creation_names=CreationNames(resource_names=user_resource_names),
                planner=SingleSiteCreationPlanner(
                    user_resources=settings.user_resources,
                    cluster_fields=settings.cluster_api.fields,
                    resource_names=user_resource_names,
                    create_database=cluster_wiring.create_database,
                    create_acl=cluster_wiring.create_acl,
                    create_role=cluster_wiring.create_role,
                    create_user=cluster_wiring.create_user,
                    update_database=cluster_wiring.update_database,
                ),
                executor=build_saga_executor(
                    settings=settings, saga_lock=saga_lock, saga_record_store=saga_record_store
                ),
                outcome_translator=CreationOutcomeTranslator(
                    resource_names=user_resource_names, public_errors=public_errors
                ),
                public_errors=public_errors,
                record_reader=saga_record_store,
                store=self.operation_store,
            ),
            acceptance=OperationAcceptance(
                store=self.operation_store,
                runner=self.task_runner,
                live_operations=live_operations,
                public_errors=public_errors,
            ),
        )


def build_saga_executor(
    *, settings: Settings, saga_lock: RedisSagaLock, saga_record_store: RedisSagaRecordStore
) -> SagaExecutor:
    failure_classifier: ClusterFailureClassifier = ClusterFailureClassifier(
        transient_error_codes=settings.cluster_api.transient_error_codes
    )
    sleeper: SystemSleeper = SystemSleeper()
    return SagaExecutor(
        record_writer=saga_record_store,
        lock=saga_lock,
        runner=StepRunner(settings=settings.saga, classifier=failure_classifier, sleeper=sleeper),
        compensator=Compensator(settings=settings.saga, classifier=failure_classifier, sleeper=sleeper),
    )
