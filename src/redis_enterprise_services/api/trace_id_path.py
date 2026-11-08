from fastapi import Request
from fastapi.exceptions import RequestValidationError

from redis_enterprise_services.config.api_settings import ApiSettings
from redis_enterprise_services.config.settings import Settings

TRACE_ID_LOCATION: tuple[str, str] = ("path", "trace_id")


def checked_trace_id(request: Request, trace_id: str) -> str:
    settings: Settings = request.app.state.settings
    api_settings: ApiSettings = settings.api
    if api_settings.trace_id_pattern.fullmatch(trace_id) is None:
        raise RequestValidationError(
            errors=[
                {"loc": TRACE_ID_LOCATION, "msg": api_settings.trace_id_error_message, "type": "value_error"}
            ]
        )
    return trace_id
