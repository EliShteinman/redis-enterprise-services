from typing import Protocol


class HeartbeatStore(Protocol):
    def refresh(self, *, trace_ids: list[str]) -> None: ...

    def delete(self, *, trace_id: str) -> None: ...
