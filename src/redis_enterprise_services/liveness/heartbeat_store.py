from typing import Protocol


class HeartbeatStore(Protocol):
    def beat(self, *, trace_ids: list[str]) -> None: ...

    def stop(self, *, trace_id: str) -> None: ...
