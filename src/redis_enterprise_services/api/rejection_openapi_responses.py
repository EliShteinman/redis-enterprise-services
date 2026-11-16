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
        HTTPStatus.UNPROCESSABLE_CONTENT: "The request does not match the contract or the traceparent "
        "header is missing or malformed (validation_error), a name breaks the naming rules (invalid_name), "
        "or the target has no configured cluster (no_matching_cluster).",
        HTTPStatus.INTERNAL_SERVER_ERROR: "configuration_error (the service configuration cannot serve the "
        "request, and the message says what in the configuration is wrong or missing) or internal_error "
        "(a fixed message; the details are in the service log, by trace_id).",
    },
)
CRDB_CREATION_ROUTE_REJECTION_RESPONSES: dict[int | str, dict[str, Any]] = rejection_openapi_responses(
    model=RejectedOperation,
    description_by_status={
        HTTPStatus.UNPROCESSABLE_CONTENT: "The request does not match the contract or the traceparent "
        "header is missing or malformed (validation_error), a name breaks the naming rules (invalid_name), "
        "a site has no configured cluster (no_matching_cluster), the sites are on more than one network "
        "(mixed_networks), or two of them resolve to the same cluster (duplicate_sites).",
        HTTPStatus.INTERNAL_SERVER_ERROR: "configuration_error (the service configuration cannot serve the "
        "request, and the message says what in the configuration is wrong or missing; when it names fields "
        "whose defaults differ between the sites, usually because the request mixes environments, sending "
        "those fields in the request avoids it) or internal_error (a fixed message; the details are in the "
        "service log, by trace_id).",
    },
)
OPERATION_ROUTE_REJECTION_RESPONSES: dict[int | str, dict[str, Any]] = rejection_openapi_responses(
    model=RejectedRequest,
    description_by_status={
        HTTPStatus.NOT_FOUND: "The trace_id is not known, or its result has expired (operation_not_found).",
        HTTPStatus.UNPROCESSABLE_CONTENT: "The traceparent header is missing or malformed, or the trace_id "
        "is not 32 lowercase hex characters, or it is all zeros (validation_error).",
        HTTPStatus.INTERNAL_SERVER_ERROR: "internal_error (a fixed message; the details are in the service "
        "log, by trace_id).",
    },
)
