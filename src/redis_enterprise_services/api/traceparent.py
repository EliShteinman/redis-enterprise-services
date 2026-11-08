from typing import Annotated

from fastapi import Header, Request
from fastapi.exceptions import RequestValidationError

from redis_enterprise_services.config.api_settings import ApiSettings
from redis_enterprise_services.config.settings import Settings

TRACEPARENT_LOCATION: tuple[str, str] = ("header", "traceparent")


def require_traceparent(request: Request, traceparent: Annotated[str | None, Header()] = None) -> None:
    app_settings: Settings = request.app.state.settings
    settings: ApiSettings = app_settings.api
    if traceparent is None or settings.traceparent_pattern.fullmatch(traceparent) is None:
        raise RequestValidationError(
            errors=[
                {
                    "loc": TRACEPARENT_LOCATION,
                    "msg": settings.traceparent_error_message,
                    "type": "value_error",
                }
            ]
        )
