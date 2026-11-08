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


class Services:
    def __init__(self, *, settings: Settings) -> None:
        silence_insecure_request_warnings()
        client: Redis = build_redis_client(settings=settings.state)
        keys: RedisKeys = RedisKeys(prefix=settings.state.key_prefix, hash_tag=settings.state.hash_tag)
        self.operations: OperationStore = RedisOperationStore(
            client=client,
            keys=keys,
            finished_operation_ttl_seconds=settings.state.finished_operation_ttl_seconds,
            heartbeat_ttl_seconds=settings.liveness.heartbeat_ttl_seconds,
        )
        self.runner: ThreadPoolTaskRunner = ThreadPoolTaskRunner(settings=settings.background)
        live_operations: LiveOperations = LiveOperations(
            heartbeat_store=RedisHeartbeatStore(
                client=client, keys=keys, heartbeat_ttl_seconds=settings.liveness.heartbeat_ttl_seconds
            )
        )
        self.heartbeat: PeriodicThread = PeriodicThread(
            name="heartbeat",
            interval_seconds=settings.liveness.heartbeat_interval_seconds,
            task=live_operations.refresh_heartbeats,
        )
        cluster: ClusterWiring = ClusterWiring(settings=settings)
        resource_names: UserResourceNames = UserResourceNames(settings=settings.user_resources)
        public_errors: PublicErrors = PublicErrors(
            settings=settings.operation, internal_error_message=settings.api.internal_error_message
        )
        lock: RedisSagaLock = RedisSagaLock(
            client=client,
            keys=keys,
            settings=settings.state.lock,
            sleeper=SystemSleeper(),
            clock=MonotonicClock(),
        )
        saga_records: RedisSagaRecordStore = RedisSagaRecordStore(
            client=client,
            keys=keys,
            finished_operation_ttl_seconds=settings.state.finished_operation_ttl_seconds,
        )
        self.sweep: PeriodicThread = PeriodicThread(
            name="abandoned operations sweep",
            interval_seconds=settings.liveness.sweep_interval_seconds,
            task=AbandonedSweep(
                store=RedisAbandonedStore(
                    client=client,
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
                        database=ListedNameLookup(lister=cluster.databases),
                        acl=ListedNameLookup(lister=cluster.acls),
                        role=ListedNameLookup(lister=cluster.roles),
                        user=ListedNameLookup(lister=cluster.users),
                    ),
                    target_resolver=cluster.target_resolver,
                ),
                creation_names=CreationNames(resource_names=resource_names),
                planner=SingleSiteCreationPlanner(
                    user_resources=settings.user_resources,
                    cluster_fields=settings.cluster_api.fields,
                    resource_names=resource_names,
                    create_database=cluster.create_database,
                    create_acl=cluster.create_acl,
                    create_role=cluster.create_role,
                    create_user=cluster.create_user,
                    update_database=cluster.update_database,
                ),
                executor=saga_executor(settings=settings, lock=lock, saga_records=saga_records),
                outcome_translator=CreationOutcomeTranslator(
                    resource_names=resource_names, public_errors=public_errors
                ),
                public_errors=public_errors,
                record_reader=saga_records,
                store=self.operations,
            ),
            acceptance=OperationAcceptance(
                store=self.operations,
                runner=self.runner,
                live_operations=live_operations,
                public_errors=public_errors,
            ),
        )


def saga_executor(
    *, settings: Settings, lock: RedisSagaLock, saga_records: RedisSagaRecordStore
) -> SagaExecutor:
    classifier: ClusterFailureClassifier = ClusterFailureClassifier(
        transient_error_codes=settings.cluster_api.transient_error_codes
    )
    sleeper: SystemSleeper = SystemSleeper()
    return SagaExecutor(
        record_writer=saga_records,
        lock=lock,
        runner=StepRunner(settings=settings.saga, classifier=classifier, sleeper=sleeper),
        compensator=Compensator(settings=settings.saga, classifier=classifier, sleeper=sleeper),
    )
