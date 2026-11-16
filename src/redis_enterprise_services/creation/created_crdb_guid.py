import logging
from uuid import UUID

from pydantic import ValidationError

from redis_enterprise_services.planning.keys.creation_step_keys import CRDB_STEP_KEY
from redis_enterprise_services.planning.planned.planned_resources import PlannedResource
from redis_enterprise_services.saga.contract.saga_record import SagaRecord
from redis_enterprise_services.steps.crdb.create_crdb import CreatedCrdb

logger: logging.Logger = logging.getLogger(name=__name__)


def created_crdb_guid(*, record: SagaRecord) -> str:
    return CreatedCrdb.model_validate(obj=record.step(key=CRDB_STEP_KEY).result).guid


def created_crdb_guid_or_none(*, record: SagaRecord, planned: PlannedResource) -> UUID | None:
    if planned.uid_step_key != CRDB_STEP_KEY:
        return None
    try:
        guid: str = created_crdb_guid(record=record)
    except ValidationError:
        return None
    try:
        return UUID(guid)
    except ValueError:
        logger.warning(msg=f"step {CRDB_STEP_KEY} holds {guid!r}, which is not a CRDB guid")
        return None
