from typing import Annotated

from fastapi import Depends, Path
from fastapi.exceptions import RequestValidationError

from redis_enterprise_services.api.app_state_dependencies import api_settings_from_app_state
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
        raise RequestValidationError(
            errors=[
                {"loc": TRACE_ID_LOCATION, "msg": api_settings.trace_id_error_message, "type": "value_error"}
            ]
        )
    return trace_id
