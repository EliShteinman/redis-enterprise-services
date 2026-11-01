from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from redis_enterprise_services.operations.error_info import ErrorInfo
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.telemetry.trace_id import current_trace_id


class FieldError(BaseModel):
    field: str = Field(
        description="Where the problem is in the request.", examples=["body.body.database.memory_size"]
    )
    message: str = Field(description="What is wrong there.", examples=["Field required"])


class ErrorDetail(ErrorInfo):
    details: list[FieldError] | None = Field(
        default=None,
        exclude_if=lambda details: details is None,
        description="Only for validation_error: every field that does not match the contract.",
    )


def error_response(*, status_code: int, error: ErrorDetail) -> JSONResponse:
    body: Operation = Operation(trace_id=current_trace_id(), status=OperationStatus.REJECTED, error=error)
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json", serialize_as_any=True))
