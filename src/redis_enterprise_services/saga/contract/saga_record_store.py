from typing import Protocol

from redis_enterprise_services.saga.contract.saga_record import SagaRecord


class SagaRecordWriter(Protocol):
    def save(self, *, record: SagaRecord) -> None: ...

    def save_final(self, *, record: SagaRecord) -> None: ...


class SagaRecordReader(Protocol):
    def find(self, *, saga_id: str) -> SagaRecord | None: ...
