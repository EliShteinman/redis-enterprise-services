from typing import Protocol

from redis_enterprise_services.saga.contract.models import SagaRecord


class SagaStateRepository(Protocol):
    def save(self, *, record: SagaRecord) -> None: ...

    def finish(self, *, record: SagaRecord) -> None: ...


class SagaRecordReader(Protocol):
    def find(self, *, saga_id: str) -> SagaRecord | None: ...
