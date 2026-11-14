from typing import Protocol


class HeartbeatStore(Protocol):
    def mark_alive(self, *, trace_ids: list[str]) -> None: ...

    def delete(self, *, trace_id: str) -> None: ...
