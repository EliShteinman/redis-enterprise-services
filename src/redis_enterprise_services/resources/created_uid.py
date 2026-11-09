from pydantic import JsonValue, ValidationError

from redis_enterprise_services.resources.models import CreatedResource


def created_uid(*, step_result: JsonValue) -> int:
    return CreatedResource.model_validate(obj=step_result).uid


def created_uid_or_none(*, step_result: JsonValue) -> int | None:
    try:
        return created_uid(step_result=step_result)
    except ValidationError:
        return None
