from pydantic import BaseModel

from redis_enterprise_services.saga.contract.saga_record import SagaRecord


class StoredSaga(BaseModel):
    raw_json: str
    record: SagaRecord | None
