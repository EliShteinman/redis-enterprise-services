from http import HTTPStatus
from typing import Any

from pydantic import BaseModel

from redis_enterprise_services.api.rejected_operation import RejectedOperation
from redis_enterprise_services.api.rejected_request import RejectedRequest


def rejection_openapi_responses(
    *, model: type[BaseModel], description_by_status: dict[HTTPStatus, str]
) -> dict[int | str, dict[str, Any]]:
    return {
        int(status): {"model": model, "description": description}
        for status, description in description_by_status.items()
    }


CREATION_ROUTE_REJECTION_RESPONSES: dict[int | str, dict[str, Any]] = rejection_openapi_responses(
    model=RejectedOperation,
    description_by_status={
        HTTPStatus.UNPROCESSABLE_CONTENT: "The request does not match the contract, the traceparent header "
        "is missing or malformed, a name breaks the naming rules, or the target has no configured cluster.",
        HTTPStatus.INTERNAL_SERVER_ERROR: "configuration_error (the service configuration cannot serve the "
        "request; the message says what is missing) or internal_error (a fixed message; the details are in "
        "the service log, by trace_id).",
    },
)
OPERATION_ROUTE_REJECTION_RESPONSES: dict[int | str, dict[str, Any]] = rejection_openapi_responses(
    model=RejectedRequest,
    description_by_status={
        HTTPStatus.NOT_FOUND: "The trace_id is not known, or its result has expired.",
        HTTPStatus.UNPROCESSABLE_CONTENT: "The traceparent header is missing or malformed, or the trace_id "
        "is not 32 lowercase hex characters, or it is all zeros.",
        HTTPStatus.INTERNAL_SERVER_ERROR: "internal_error (a fixed message; the details are in the service "
        "log, by trace_id).",
    },
)
