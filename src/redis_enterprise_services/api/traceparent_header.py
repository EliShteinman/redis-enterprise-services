from typing import Annotated

from fastapi import Depends, Header

from redis_enterprise_services.api.app_state_dependencies import api_settings_from_app_state
from redis_enterprise_services.api.field_validation_error import field_validation_error
from redis_enterprise_services.config.api_settings import ApiSettings

TRACEPARENT_LOCATION: tuple[str, str] = ("header", "traceparent")


def require_traceparent(
    api_settings: Annotated[ApiSettings, Depends(dependency=api_settings_from_app_state)],
    traceparent: Annotated[
        str,
        Header(
            description="The W3C traceparent of the call. Its trace id is the trace_id of the operation.",
            examples=["00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"],
        ),
    ],
) -> None:
    if api_settings.traceparent_pattern.fullmatch(traceparent) is None:
        raise field_validation_error(
            location=TRACEPARENT_LOCATION, message=api_settings.traceparent_error_message
        )
