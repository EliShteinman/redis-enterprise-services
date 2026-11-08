from pydantic import BaseModel

from redis_enterprise_services.saga.contract.saga_record import SagaRecord


class StoredSaga(BaseModel):
    raw: str
    record: SagaRecord
