from redis import Redis

from redis_enterprise_services.background.thread_pool_runner import ThreadPoolRunner
from redis_enterprise_services.composition.cluster_wiring import ClusterWiring
from redis_enterprise_services.config.settings import Settings
from redis_enterprise_services.creation.creation_execution import CreationExecution
from redis_enterprise_services.creation.creation_outcome import CreationOutcome
from redis_enterprise_services.creation.creation_preparation import CreationPreparation
from redis_enterprise_services.creation.database_creation import DatabaseCreation
from redis_enterprise_services.edge.insecure_warnings import silence_insecure_request_warnings
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.planning.availability.chosen_cluster_scope import ChosenClusterScope
from redis_enterprise_services.planning.availability.creation_names import CreationNames
from redis_enterprise_services.planning.availability.listed_name_lookup import ListedNameLookup
from redis_enterprise_services.planning.availability.name_availability import NameAvailability
from redis_enterprise_services.planning.availability.name_lookups import NameLookups
from redis_enterprise_services.planning.cluster_directory import ClusterDirectory
from redis_enterprise_services.planning.cluster_resolver import ClusterResolver
from redis_enterprise_services.planning.database_defaults import DatabaseDefaults
from redis_enterprise_services.planning.naming.name_rules_factory import configured_name_rules
from redis_enterprise_services.planning.naming.name_validator import NameValidator
from redis_enterprise_services.planning.resource_names import ResourceNames
from redis_enterprise_services.planning.single_candidate_chooser import SingleCandidateChooser
from redis_enterprise_services.planning.single_site_creation import SingleSiteCreationPlanner
from redis_enterprise_services.saga.engine.compensator import Compensator
from redis_enterprise_services.saga.engine.executor import SagaExecutor
from redis_enterprise_services.saga.engine.step_runner import StepRunner
from redis_enterprise_services.state.redis_client import build_redis_client
from redis_enterprise_services.state.redis_database_lock import RedisDatabaseLock
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.state.redis_operation_store import RedisOperationStore
from redis_enterprise_services.state.redis_saga_state import RedisSagaState
from redis_enterprise_services.steps.failure_classifier import ClusterFailureClassifier
from redis_enterprise_services.timing.clock import MonotonicClock
from redis_enterprise_services.timing.sleeper import SystemSleeper


class Services:
    def __init__(self, *, settings: Settings) -> None:
        silence_insecure_request_warnings()
        client: Redis = build_redis_client(settings=settings.state)
        keys: RedisKeys = RedisKeys(prefix=settings.state.prefix, hash_tag=settings.state.hash_tag)
        self.operations: OperationStore = RedisOperationStore(
            client=client, keys=keys, finished_ttl_seconds=settings.state.finished_ttl_seconds
        )
        self.runner: ThreadPoolRunner = ThreadPoolRunner(settings=settings.background)
        cluster: ClusterWiring = ClusterWiring(settings=settings)
        names: ResourceNames = ResourceNames(settings=settings.decomposition)
        errors: PublicErrors = PublicErrors(
            settings=settings.operation, internal_error_message=settings.api.internal_error_message
        )
        saga_state: RedisSagaState = RedisSagaState(
            client=client, keys=keys, finished_ttl_seconds=settings.state.finished_ttl_seconds
        )
        self.database_creation: DatabaseCreation = DatabaseCreation(
            preparation=CreationPreparation(
                validator=NameValidator(rules=configured_name_rules(settings=settings.naming.database)),
                resolver=ClusterResolver(
                    directory=ClusterDirectory(clusters=settings.clusters), chooser=SingleCandidateChooser()
                ),
                defaults=DatabaseDefaults(settings=settings.database_defaults),
            ),
            execution=CreationExecution(
                scope=ChosenClusterScope(),
                availability=NameAvailability(
                    lookups=NameLookups(
                        database=ListedNameLookup(lister=cluster.databases),
                        acl=ListedNameLookup(lister=cluster.acls),
                        role=ListedNameLookup(lister=cluster.roles),
                        user=ListedNameLookup(lister=cluster.users),
                    ),
                    credentials=cluster.credentials,
                ),
                names=CreationNames(names=names),
                planner=SingleSiteCreationPlanner(
                    settings=settings.decomposition,
                    names=names,
                    create_database=cluster.create_database,
                    create_acl=cluster.create_acl,
                    create_role=cluster.create_role,
                    create_user=cluster.create_user,
                    update_database=cluster.update_database,
                ),
                executor=saga_executor(settings=settings, client=client, keys=keys, state=saga_state),
                outcome=CreationOutcome(names=names, errors=errors),
                errors=errors,
                records=saga_state,
                store=self.operations,
            ),
            store=self.operations,
            runner=self.runner,
        )


def saga_executor(
    *, settings: Settings, client: Redis, keys: RedisKeys, state: RedisSagaState
) -> SagaExecutor:
    classifier: ClusterFailureClassifier = ClusterFailureClassifier(
        transient_codes=settings.cluster.transient_error_codes
    )
    sleeper: SystemSleeper = SystemSleeper()
    return SagaExecutor(
        state=state,
        lock=RedisDatabaseLock(
            client=client, keys=keys, settings=settings.state.lock, sleeper=sleeper, clock=MonotonicClock()
        ),
        runner=StepRunner(settings=settings.saga, classifier=classifier, sleeper=sleeper),
        compensator=Compensator(settings=settings.saga, classifier=classifier, sleeper=sleeper),
    )
