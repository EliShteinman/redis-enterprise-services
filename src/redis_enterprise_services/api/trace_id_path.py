from typing import Annotated

from fastapi import Depends
from fastapi.exceptions import RequestValidationError

from redis_enterprise_services.api.app_state_dependencies import api_settings_from_app_state
from redis_enterprise_services.config.api_settings import ApiSettings

TRACE_ID_LOCATION: tuple[str, str] = ("path", "trace_id")


def checked_trace_id(
    trace_id: str, api_settings: Annotated[ApiSettings, Depends(dependency=api_settings_from_app_state)]
) -> str:
    if api_settings.trace_id_pattern.fullmatch(trace_id) is None:
        raise RequestValidationError(
            errors=[
                {"loc": TRACE_ID_LOCATION, "msg": api_settings.trace_id_error_message, "type": "value_error"}
            ]
        )
    return trace_id
