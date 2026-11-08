import logging
from http import HTTPStatus

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from redis_enterprise_services.api.rejection_response import (
    DetailedPublicError,
    FieldError,
    rejection_response,
)
from redis_enterprise_services.config.api_settings import ApiSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError

VALIDATION_ERROR_CODE: str = "validation_error"
FIELD_PATH_SEPARATOR: str = "."

logger: logging.Logger = logging.getLogger(name=__name__)


def field_path(*, location: tuple[int | str, ...]) -> str:
    return FIELD_PATH_SEPARATOR.join(str(part) for part in location)


async def service_error_handler(request: Request, error: RedisEnterpriseServicesError) -> Response:
    level: int = logging.ERROR if error.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR else logging.WARNING
    logger.log(level=level, msg=f"{error.code}: {error.message}")
    return rejection_response(
        status_code=error.status_code, error=DetailedPublicError(code=error.code, message=error.message)
    )


class ValidationErrorHandler:
    def __init__(self, *, settings: ApiSettings) -> None:
        self._settings: ApiSettings = settings

    async def __call__(self, request: Request, error: RequestValidationError) -> Response:
        field_errors: list[FieldError] = [
            FieldError(field=field_path(location=detail["loc"]), message=detail["msg"])
            for detail in error.errors()
        ]
        logger.info(msg=f"{VALIDATION_ERROR_CODE}: {[detail.field for detail in field_errors]}")
        return rejection_response(
            status_code=HTTPStatus.UNPROCESSABLE_CONTENT,
            error=DetailedPublicError(
                code=VALIDATION_ERROR_CODE,
                message=self._settings.validation_error_message,
                details=field_errors,
            ),
        )


async def http_exception_handler(request: Request, error: HTTPException) -> Response:
    code: str = HTTPStatus(value=error.status_code).name.lower()
    logger.info(msg=f"{code}: {request.method} {request.url.path}")
    response: Response = rejection_response(
        status_code=error.status_code, error=DetailedPublicError(code=code, message=str(error.detail))
    )
    response.headers.update(error.headers or {})
    return response
