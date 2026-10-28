from typing import Protocol

from redis_enterprise_services.saga.models import SagaRecord


class SagaStateRepository(Protocol):
    def save(self, *, record: SagaRecord) -> None: ...

    def finish(self, *, record: SagaRecord) -> None: ...
