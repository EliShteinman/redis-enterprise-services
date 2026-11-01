from typing import Protocol

from redis_enterprise_services.operations.operation import Operation


class OperationStore(Protocol):
    def save(self, *, operation: Operation) -> None: ...

    def find(self, *, trace_id: str) -> Operation | None: ...
