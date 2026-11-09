from typing import Annotated

from fastapi import Depends, Path

from redis_enterprise_services.api.app_state_dependencies import api_settings_from_app_state
from redis_enterprise_services.api.field_validation_error import field_validation_error
from redis_enterprise_services.config.api_settings import ApiSettings

TRACE_ID_LOCATION: tuple[str, str] = ("path", "trace_id")


def checked_trace_id(
    trace_id: Annotated[
        str,
        Path(
            description="The trace_id the command returned: 32 lowercase hex characters, not all zeros.",
            examples=["4bf92f3577b34da6a3ce929d0e0e4736"],
        ),
    ],
    api_settings: Annotated[ApiSettings, Depends(dependency=api_settings_from_app_state)],
) -> str:
    if api_settings.trace_id_pattern.fullmatch(trace_id) is None:
        raise field_validation_error(location=TRACE_ID_LOCATION, message=api_settings.trace_id_error_message)
    return trace_id
