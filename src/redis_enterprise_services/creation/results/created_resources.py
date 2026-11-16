from pydantic import ValidationError

from redis_enterprise_services.resources.models import CreatedResource
from redis_enterprise_services.saga.contract.saga_record import SagaRecord


def created_resource(*, record: SagaRecord, step_key: str) -> CreatedResource:
    return CreatedResource.model_validate(obj=record.step(key=step_key).result)


def created_uid_or_none(*, record: SagaRecord, step_key: str) -> int | None:
    try:
        return created_resource(record=record, step_key=step_key).uid
    except ValidationError:
        return None
