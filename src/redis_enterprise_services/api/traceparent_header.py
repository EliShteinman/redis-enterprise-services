from typing import Annotated

from fastapi import Depends, Header
from fastapi.exceptions import RequestValidationError

from redis_enterprise_services.api.app_state_dependencies import api_settings_from_app_state
from redis_enterprise_services.config.api_settings import ApiSettings

TRACEPARENT_LOCATION: tuple[str, str] = ("header", "traceparent")


def require_traceparent(
    api_settings: Annotated[ApiSettings, Depends(dependency=api_settings_from_app_state)],
    traceparent: Annotated[str | None, Header()] = None,
) -> None:
    if traceparent is None or api_settings.traceparent_pattern.fullmatch(traceparent) is None:
        raise RequestValidationError(
            errors=[
                {
                    "loc": TRACEPARENT_LOCATION,
                    "msg": api_settings.traceparent_error_message,
                    "type": "value_error",
                }
            ]
        )
