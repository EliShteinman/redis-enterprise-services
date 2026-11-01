from typing import Protocol

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.saga.contract.models import SagaRecord


class AbandonedStore(Protocol):
    def without_heartbeat(self) -> list[str]: ...

    def mark_abandoned(self, *, operation: Operation, stopped_saga: SagaRecord | None) -> bool: ...
