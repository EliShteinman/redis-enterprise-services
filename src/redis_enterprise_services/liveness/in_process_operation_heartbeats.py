import logging
from collections.abc import Callable
from threading import Lock

from redis_enterprise_services.liveness.heartbeat_store import HeartbeatStore
from redis_enterprise_services.liveness.operation_heartbeats import OperationHeartbeats

logger: logging.Logger = logging.getLogger(name=__name__)


class InProcessOperationHeartbeats(OperationHeartbeats):
    def __init__(self, *, heartbeat_store: HeartbeatStore) -> None:
        self._heartbeat_store: HeartbeatStore = heartbeat_store
        self._lock: Lock = Lock()
        self._tracked_trace_ids: set[str] = set()

    def track(self, *, trace_id: str) -> None:
        with self._lock:
            self._tracked_trace_ids.add(trace_id)

    def stop_heartbeat(self, *, trace_id: str) -> None:
        with self._lock:
            self._tracked_trace_ids.discard(trace_id)
            self._heartbeat_store.delete(trace_id=trace_id)

    def stopping_heartbeat_when_done(
        self, *, trace_id: str, task: Callable[[], object]
    ) -> Callable[[], object]:
        def run_then_stop_heartbeat() -> object:
            try:
                return task()
            finally:
                self.stop_heartbeat(trace_id=trace_id)

        return run_then_stop_heartbeat

    def mark_tracked_alive(self) -> None:
        with self._lock:
            if self._tracked_trace_ids:
                self._heartbeat_store.mark_alive(trace_ids=sorted(self._tracked_trace_ids))
