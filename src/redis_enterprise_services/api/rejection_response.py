from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.telemetry.trace_id import current_trace_id_or_zeros


class FieldError(BaseModel):
    field: str = Field(
        description="Where the problem is in the request.", examples=["body.spec.database.memory_size"]
    )
    message: str = Field(description="What is wrong there.", examples=["Field required"])


class DetailedPublicError(PublicError):
    details: list[FieldError] | None = Field(
        default=None,
        exclude_if=lambda details: details is None,
        description="Only for validation_error: every field that does not match the contract.",
    )


def rejection_response(*, status_code: int, error: DetailedPublicError) -> JSONResponse:
    rejected_operation: Operation = Operation(
        trace_id=current_trace_id_or_zeros(), status=OperationStatus.REJECTED, error=error
    )
    return JSONResponse(
        status_code=status_code, content=rejected_operation.model_dump(mode="json", serialize_as_any=True)
    )
