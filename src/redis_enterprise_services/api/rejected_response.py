from http import HTTPStatus
from typing import Any

from pydantic import BaseModel, Field

from redis_enterprise_services.api.error_response import ErrorDetail
from redis_enterprise_services.operations.operation_status import OperationStatus


class RejectedResponse(BaseModel):
    trace_id: str = Field(
        description="The trace ID of the request.", examples=["4bf92f3577b34da6a3ce929d0e0e4736"]
    )
    status: OperationStatus = Field(
        description="Always rejected: nothing was changed.", examples=["rejected"]
    )
    database: None = Field(default=None, description="Always null.")
    error: ErrorDetail = Field(description="Why the request was refused.")


def rejected_responses(*, statuses: dict[HTTPStatus, str]) -> dict[int | str, dict[str, Any]]:
    return {
        int(status): {"model": RejectedResponse, "description": description}
        for status, description in statuses.items()
    }


COMMAND_REJECTIONS: dict[int | str, dict[str, Any]] = rejected_responses(
    statuses={
        HTTPStatus.UNPROCESSABLE_CONTENT: "The request does not match the contract, a name breaks the naming "
        "rules, or the target has no configured cluster.",
        HTTPStatus.INTERNAL_SERVER_ERROR: "configuration_error (the service configuration cannot serve the "
        "request) or internal_error (a bug). The details are in the service log, by trace_id.",
    }
)
STATUS_REJECTIONS: dict[int | str, dict[str, Any]] = rejected_responses(
    statuses={
        HTTPStatus.NOT_FOUND: "The trace_id is not known, or its result has expired.",
        HTTPStatus.UNPROCESSABLE_CONTENT: "The traceparent header is missing or malformed.",
    }
)
