from collections.abc import Mapping

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from redis_enterprise_services.api.command_route import is_command_request
from redis_enterprise_services.api.rejected_operation import RejectedOperation
from redis_enterprise_services.api.rejected_request import RejectedRequest
from redis_enterprise_services.api.rejection_error import RejectionError
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.telemetry.trace_id import current_trace_id_or_zeros


def rejection_response(
    *, request: Request, status_code: int, error: RejectionError, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=rejection_body(request=request, error=error).model_dump(mode="json"),
        headers=headers,
    )


def rejection_body(*, request: Request, error: RejectionError) -> BaseModel:
    trace_id: str = current_trace_id_or_zeros()
    if is_command_request(request=request):
        return RejectedOperation(trace_id=trace_id, status=OperationStatus.REJECTED, error=error)
    return RejectedRequest(trace_id=trace_id, error=error)
