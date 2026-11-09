import logging
from collections.abc import Sequence
from http import HTTPStatus
from typing import Any

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from redis_enterprise_services.api.rejection_response import (
    FieldError,
    RejectionError,
    rejection_response,
)
from redis_enterprise_services.config.api_settings import ApiSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError

VALIDATION_ERROR_CODE: str = "validation_error"
LOCATION_SEPARATOR: str = "."

logger: logging.Logger = logging.getLogger(name=__name__)
UNKNOWN_HTTP_ERROR_CODE: str = "http_error"


def dotted_location(*, location: tuple[int | str, ...]) -> str:
    return LOCATION_SEPARATOR.join(str(part) for part in location)


async def service_error_handler(request: Request, error: RedisEnterpriseServicesError) -> Response:
    logger.log(
        level=log_level_for_status(status_code=error.status_code), msg=f"{error.code}: {error.message}"
    )
    return rejection_response(
        status_code=error.status_code,
        error=RejectionError(code=error.code, message=error.message),
    )


class ValidationErrorHandler:
    def __init__(self, *, settings: ApiSettings) -> None:
        self._settings: ApiSettings = settings

    async def __call__(self, request: Request, error: RequestValidationError) -> Response:
        field_errors: list[FieldError] = field_errors_from(error_details=error.errors())
        logger.info(msg=f"{VALIDATION_ERROR_CODE}: {[detail.location for detail in field_errors]}")
        return rejection_response(
            status_code=HTTPStatus.UNPROCESSABLE_CONTENT,
            error=RejectionError(
                code=VALIDATION_ERROR_CODE,
                message=self._settings.validation_error_message,
                details=field_errors,
            ),
        )


async def http_exception_handler(request: Request, error: HTTPException) -> Response:
    code: str = http_error_code(status_code=error.status_code)
    logger.info(msg=f"{code}: {request.method} {request.url.path}")
    return rejection_response(
        status_code=error.status_code,
        error=RejectionError(code=code, message=str(error.detail)),
        headers=error.headers,
    )


def log_level_for_status(*, status_code: int) -> int:
    return logging.ERROR if status_code >= HTTPStatus.INTERNAL_SERVER_ERROR else logging.WARNING


def http_error_code(*, status_code: int) -> str:
    try:
        return HTTPStatus(value=status_code).name.lower()
    except ValueError:
        return UNKNOWN_HTTP_ERROR_CODE


def field_errors_from(*, error_details: Sequence[Any]) -> list[FieldError]:
    return [
        FieldError(location=dotted_location(location=detail["loc"]), message=detail["msg"])
        for detail in error_details
    ]
