from pydantic import BaseModel

from redis_enterprise_services.saga.contract.models import SagaRecord


class StoredSaga(BaseModel):
    raw: str
    record: SagaRecord
