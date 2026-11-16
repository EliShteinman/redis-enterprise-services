from redis_enterprise_services.background.periodic_thread import PeriodicThread
from redis_enterprise_services.background.thread_pool_task_runner import ThreadPoolTaskRunner
from redis_enterprise_services.config.background_settings import BackgroundSettings
from redis_enterprise_services.config.liveness_settings import LivenessSettings
from redis_enterprise_services.liveness.heartbeat_store import HeartbeatStore
from redis_enterprise_services.liveness.in_process_operation_heartbeats import InProcessOperationHeartbeats
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.recovery.abandoned_store import AbandonedStore
from redis_enterprise_services.recovery.abandoned_sweep import AbandonedSweep

OPERATION_HEARTBEAT_THREAD_NAME: str = "operation heartbeat"
ABANDONED_SWEEP_THREAD_NAME: str = "abandoned operations sweep"


class BackgroundWiring:
    def __init__(
        self,
        *,
        background: BackgroundSettings,
        liveness: LivenessSettings,
        heartbeat_store: HeartbeatStore,
        abandoned_store: AbandonedStore,
        public_errors: PublicErrors,
    ) -> None:
        self.task_runner: ThreadPoolTaskRunner = ThreadPoolTaskRunner(settings=background)
        self.operation_heartbeats: InProcessOperationHeartbeats = InProcessOperationHeartbeats(
            heartbeat_store=heartbeat_store
        )
        self._operation_heartbeat_thread: PeriodicThread = PeriodicThread(
            name=OPERATION_HEARTBEAT_THREAD_NAME,
            interval_seconds=liveness.heartbeat_interval_seconds,
            task=self.operation_heartbeats.mark_tracked_alive,
        )
        self._abandoned_sweep_thread: PeriodicThread = PeriodicThread(
            name=ABANDONED_SWEEP_THREAD_NAME,
            interval_seconds=liveness.abandoned_sweep_interval_seconds,
            task=AbandonedSweep(store=abandoned_store, public_errors=public_errors).sweep,
        )

    def start(self) -> None:
        self._operation_heartbeat_thread.start()
        self._abandoned_sweep_thread.start()

    def stop(self) -> None:
        self._abandoned_sweep_thread.stop()
        self.task_runner.close()
        self._operation_heartbeat_thread.stop()
