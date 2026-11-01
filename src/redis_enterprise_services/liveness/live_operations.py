import logging
from collections.abc import Callable
from threading import Lock

from redis_enterprise_services.liveness.heartbeat_store import HeartbeatStore

logger: logging.Logger = logging.getLogger(name=__name__)


class LiveOperations:
    def __init__(self, *, store: HeartbeatStore) -> None:
        self._store: HeartbeatStore = store
        self._lock: Lock = Lock()
        self._trace_ids: set[str] = set()

    def track(self, *, trace_id: str) -> None:
        with self._lock:
            self._trace_ids.add(trace_id)

    def release(self, *, trace_id: str) -> None:
        with self._lock:
            self._trace_ids.discard(trace_id)
            self._store.stop(trace_id=trace_id)

    def released_after(self, *, trace_id: str, task: Callable[[], object]) -> Callable[[], object]:
        def run_then_release() -> object:
            try:
                return task()
            finally:
                self.release(trace_id=trace_id)

        return run_then_release

    def beat_all(self) -> None:
        with self._lock:
            if self._trace_ids:
                self._store.beat(trace_ids=sorted(self._trace_ids))
