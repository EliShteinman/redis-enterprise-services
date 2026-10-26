from typing import Literal

from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from redis_enterprise_services.telemetry.trace_id import current_trace_id


class FieldError(BaseModel):
    field: str
    message: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[FieldError] | None = Field(default=None, exclude_if=lambda details: details is None)


class ErrorResponse(BaseModel):
    trace_id: str
    status: Literal["rejected"] = "rejected"
    database: None = None
    error: ErrorDetail


def error_response(*, status_code: int, error: ErrorDetail) -> JSONResponse:
    body: ErrorResponse = ErrorResponse(trace_id=current_trace_id(), error=error)
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))
