import logging
from collections.abc import Sequence
from http import HTTPStatus
from typing import Any

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from redis_enterprise_services.api.rejection_error import FieldError, RejectionError
from redis_enterprise_services.api.rejection_response import rejection_response
from redis_enterprise_services.config.api_settings import ApiSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.operation import OperationNotFoundError
from redis_enterprise_services.operations.public_errors import PublicErrors

VALIDATION_ERROR_CODE: str = "validation_error"
LOCATION_SEPARATOR: str = "."
UNKNOWN_HTTP_ERROR_CODE: str = "http_error"
API_ONLY_ERROR_CODES: frozenset[str] = frozenset({OperationNotFoundError.code})

logger: logging.Logger = logging.getLogger(name=__name__)


def dotted_location(*, location: tuple[int | str, ...]) -> str:
    return LOCATION_SEPARATOR.join(str(part) for part in location)


class ServiceErrorHandler:
    def __init__(self, *, public_errors: PublicErrors) -> None:
        self._public_errors: PublicErrors = public_errors

    async def __call__(self, request: Request, error: RedisEnterpriseServicesError) -> Response:
        logger.log(
            level=log_level_for_status(status_code=error.status_code), msg=f"{error.code}: {error.message}"
        )
        return rejection_response(
            request=request, status_code=error.status_code, error=self._rejection_error(error=error)
        )

    def _rejection_error(self, *, error: RedisEnterpriseServicesError) -> RejectionError:
        public_code: str = self._public_code(internal_code=error.code)
        if public_code == RedisEnterpriseServicesError.code:
            return RejectionError(code=public_code, message=self._public_errors.internal_error().message)
        return RejectionError(code=public_code, message=error.message)

    def _public_code(self, *, internal_code: str) -> str:
        if internal_code in API_ONLY_ERROR_CODES:
            return internal_code
        return self._public_errors.public_code(internal_code=internal_code)


class ValidationErrorHandler:
    def __init__(self, *, settings: ApiSettings) -> None:
        self._settings: ApiSettings = settings

    async def __call__(self, request: Request, error: RequestValidationError) -> Response:
        field_errors: list[FieldError] = field_errors_from(error_details=error.errors())
        logger.info(msg=f"{VALIDATION_ERROR_CODE}: {[detail.location for detail in field_errors]}")
        return rejection_response(
            request=request,
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
        request=request,
        status_code=error.status_code,
        error=RejectionError(code=code, message=str(error.detail)),
        headers=error.headers,
    )


def log_level_for_status(*, status_code: int) -> int:
    return logging.ERROR if status_code >= HTTPStatus.INTERNAL_SERVER_ERROR else logging.INFO


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
