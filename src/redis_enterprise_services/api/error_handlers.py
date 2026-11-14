import logging
from collections.abc import Sequence
from http import HTTPStatus
from typing import Any

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from redis_enterprise_services.api.internal_error_report import report_internal_error
from redis_enterprise_services.api.rejection_error import FieldError, RejectionError
from redis_enterprise_services.api.rejection_error_code import (
    API_ERROR_CODE_BY_HTTP_STATUS,
    API_ERROR_CODE_BY_INTERNAL_CODE,
    UNKNOWN_HTTP_ERROR_CODE,
    VALIDATION_ERROR_CODE,
    RejectionErrorCode,
)
from redis_enterprise_services.api.rejection_response import rejection_response
from redis_enterprise_services.api.service_rejection import ServiceRejection, service_rejection
from redis_enterprise_services.config.api_settings import ApiSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.operations.public_errors import PublicErrors

LOCATION_SEPARATOR: str = "."

logger: logging.Logger = logging.getLogger(name=__name__)


def dotted_location(*, location: tuple[int | str, ...]) -> str:
    return LOCATION_SEPARATOR.join(str(part) for part in location)


class ServiceErrorHandler:
    def __init__(self, *, public_errors: PublicErrors) -> None:
        self._public_errors: PublicErrors = public_errors

    async def __call__(self, request: Request, error: RedisEnterpriseServicesError) -> Response:
        public_code: RejectionErrorCode = self._public_code(internal_code=error.code)
        rejection: ServiceRejection = service_rejection(
            error=error,
            public_code=public_code,
            kind=self._public_errors.kind_of(code=public_code),
            internal_error_message=self._public_errors.internal_error().message,
        )
        log_service_error(error=error, status_code=rejection.status_code)
        return rejection_response(request=request, status_code=rejection.status_code, error=rejection.error)

    def _public_code(self, *, internal_code: str) -> RejectionErrorCode:
        return API_ERROR_CODE_BY_INTERNAL_CODE.get(internal_code) or self._public_errors.public_code(
            internal_code=internal_code
        )


class ValidationErrorHandler:
    def __init__(self, *, settings: ApiSettings, public_errors: PublicErrors) -> None:
        self._settings: ApiSettings = settings
        self._public_errors: PublicErrors = public_errors

    async def __call__(self, request: Request, error: RequestValidationError) -> Response:
        field_errors: list[FieldError] = field_errors_from(error_details=error.errors())
        logger.info(msg=f"{VALIDATION_ERROR_CODE}: {[detail.location for detail in field_errors]}")
        return rejection_response(
            request=request,
            status_code=HTTPStatus.UNPROCESSABLE_CONTENT,
            error=RejectionError(
                code=VALIDATION_ERROR_CODE,
                kind=self._public_errors.kind_of(code=VALIDATION_ERROR_CODE),
                message=self._settings.validation_error_message,
                details=field_errors,
            ),
        )


class HttpErrorHandler:
    def __init__(self, *, public_errors: PublicErrors) -> None:
        self._public_errors: PublicErrors = public_errors

    async def __call__(self, request: Request, error: HTTPException) -> Response:
        code: RejectionErrorCode = http_error_code(status_code=error.status_code)
        logger.info(msg=f"{code}: {request.method} {request.url.path}")
        return rejection_response(
            request=request,
            status_code=error.status_code,
            error=RejectionError(
                code=code, kind=self._public_errors.kind_of(code=code), message=str(error.detail)
            ),
            headers=error.headers,
        )


def log_service_error(*, error: RedisEnterpriseServicesError, status_code: int) -> None:
    if status_code < HTTPStatus.INTERNAL_SERVER_ERROR:
        logger.info(msg=error.coded_message())
        return
    report_internal_error(error=error, message=error.coded_message())


def http_error_code(*, status_code: int) -> RejectionErrorCode:
    return API_ERROR_CODE_BY_HTTP_STATUS.get(status_code, UNKNOWN_HTTP_ERROR_CODE)


def field_errors_from(*, error_details: Sequence[Any]) -> list[FieldError]:
    return [
        FieldError(location=dotted_location(location=detail["loc"]), message=detail["msg"])
        for detail in error_details
    ]
