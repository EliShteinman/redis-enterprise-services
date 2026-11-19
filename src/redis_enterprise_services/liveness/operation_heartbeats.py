from collections.abc import Callable
from typing import Protocol


class OperationHeartbeats(Protocol):
    def track(self, *, trace_id: str) -> None: ...

    def stop_heartbeat(self, *, trace_id: str) -> None: ...

    def stopping_heartbeat_when_done(
        self, *, trace_id: str, task: Callable[[], object]
    ) -> Callable[[], object]: ...
