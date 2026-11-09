from http import HTTPStatus
from typing import Literal

from redis_enterprise_services.config.public_error_code import PublicErrorCode
from redis_enterprise_services.exceptions.operation import OperationNotFoundError

type ApiErrorCode = Literal[
    "validation_error", "not_found", "operation_not_found", "method_not_allowed", "http_error"
]
type RejectionErrorCode = PublicErrorCode | ApiErrorCode

VALIDATION_ERROR_CODE: ApiErrorCode = "validation_error"
UNKNOWN_HTTP_ERROR_CODE: ApiErrorCode = "http_error"
API_ERROR_CODE_BY_INTERNAL_CODE: dict[str, ApiErrorCode] = {
    OperationNotFoundError.code: "operation_not_found"
}
API_ERROR_CODE_BY_HTTP_STATUS: dict[int, ApiErrorCode] = {
    HTTPStatus.NOT_FOUND: "not_found",
    HTTPStatus.METHOD_NOT_ALLOWED: "method_not_allowed",
}
API_ERROR_CODE_DESCRIPTION: str = (
    "validation_error (the request does not match), "
    "not_found (unknown path), "
    "operation_not_found (unknown or expired trace id), "
    "method_not_allowed (the path does not take this method), "
    "http_error (another HTTP error, with its own status), "
)
