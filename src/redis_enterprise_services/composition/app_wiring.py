from redis_enterprise_services.composition.background_wiring import BackgroundWiring
from redis_enterprise_services.composition.cluster.cluster_wiring import ClusterWiring
from redis_enterprise_services.composition.creation.creation_wiring import CreationWiring
from redis_enterprise_services.composition.state_wiring import StateWiring
from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.service.api_settings import ApiSettings
from redis_enterprise_services.config.service.operation_settings import OperationSettings
from redis_enterprise_services.config.settings import Settings
from redis_enterprise_services.creation.crdb_creation import CrdbCreation
from redis_enterprise_services.creation.database_creation import DatabaseCreation
from redis_enterprise_services.operations.errors.public_errors import PublicErrors
from redis_enterprise_services.operations.operation_store import OperationStore
from redis_enterprise_services.timing.clock import MonotonicClock
from redis_enterprise_services.timing.deadline_polling import DeadlinePolling
from redis_enterprise_services.timing.sleeper import SystemSleeper


class AppWiring:
    def __init__(self, *, settings: Settings) -> None:
        sleeper: SystemSleeper = SystemSleeper()
        deadline_polling: DeadlinePolling = DeadlinePolling(clock=MonotonicClock(), sleeper=sleeper)
        clusters: list[ConfiguredCluster] = settings.flattened_clusters()
        self.public_errors: PublicErrors = build_public_errors(operation=settings.operation, api=settings.api)
        self._state_wiring: StateWiring = StateWiring(
            state=settings.state, liveness=settings.liveness, deadline_polling=deadline_polling
        )
        self._cluster_wiring: ClusterWiring = ClusterWiring(
            settings=settings, clusters=clusters, deadline_polling=deadline_polling
        )
        self._background_wiring: BackgroundWiring = BackgroundWiring(
            background=settings.background,
            liveness=settings.liveness,
            heartbeat_store=self._state_wiring.heartbeat_store,
            abandoned_store=self._state_wiring.abandoned_store,
            public_errors=self.public_errors,
        )
        self.operation_store: OperationStore = self._state_wiring.operation_store
        creation_wiring: CreationWiring = CreationWiring(
            settings=settings,
            clusters=clusters,
            cluster_wiring=self._cluster_wiring,
            state_wiring=self._state_wiring,
            background_wiring=self._background_wiring,
            public_errors=self.public_errors,
            sleeper=sleeper,
        )
        self.database_creation: DatabaseCreation = creation_wiring.database_creation
        self.crdb_creation: CrdbCreation = creation_wiring.crdb_creation

    def start(self) -> None:
        self._background_wiring.start()

    def stop(self) -> None:
        self._background_wiring.stop()
        self._cluster_wiring.close()
        self._state_wiring.close()


def build_public_errors(*, operation: OperationSettings, api: ApiSettings) -> PublicErrors:
    return PublicErrors(
        settings=operation,
        internal_error_message=api.internal_error_message,
        unexpected_error_message=api.unexpected_error_message,
    )
