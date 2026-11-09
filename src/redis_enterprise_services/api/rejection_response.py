from collections.abc import Mapping

from fastapi import Request
from fastapi.responses import JSONResponse

from redis_enterprise_services.api.command_route import is_command_request
from redis_enterprise_services.api.operation_json_response import operation_json_response
from redis_enterprise_services.api.rejected_request import RejectedRequest
from redis_enterprise_services.api.rejection_error import RejectionError
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.telemetry.trace_id import current_trace_id_or_zeros


def rejection_response(
    *, request: Request, status_code: int, error: RejectionError, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    if is_command_request(request=request):
        return rejected_command_response(status_code=status_code, error=error, headers=headers)
    return rejected_request_response(status_code=status_code, error=error, headers=headers)


def rejected_command_response(
    *, status_code: int, error: RejectionError, headers: Mapping[str, str] | None
) -> JSONResponse:
    return operation_json_response(
        operation=Operation.rejected(trace_id=current_trace_id_or_zeros(), error=error),
        status_code=status_code,
        headers=headers,
    )


def rejected_request_response(
    *, status_code: int, error: RejectionError, headers: Mapping[str, str] | None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=RejectedRequest(trace_id=current_trace_id_or_zeros(), error=error).model_dump(
            mode="json", serialize_as_any=True
        ),
        headers=headers,
    )
