import logging
from http import HTTPStatus

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from redis_enterprise_services.api.app_settings import api_settings
from redis_enterprise_services.api.error_response import ErrorDetail, FieldError, error_response
from redis_enterprise_services.config.api_settings import ApiSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError

FIELD_PATH_SEPARATOR: str = "."

logger: logging.Logger = logging.getLogger(name=__name__)


def field_path(*, location: tuple[int | str, ...]) -> str:
    return FIELD_PATH_SEPARATOR.join(str(part) for part in location)


async def project_error_handler(request: Request, error: RedisEnterpriseServicesError) -> Response:
    level: int = logging.ERROR if error.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR else logging.WARNING
    logger.log(level=level, msg=f"{error.code}: {error.message}")
    return error_response(
        status_code=error.status_code, error=ErrorDetail(code=error.code, message=error.message)
    )


async def validation_error_handler(request: Request, error: RequestValidationError) -> Response:
    details: list[FieldError] = [
        FieldError(field=field_path(location=detail["loc"]), message=detail["msg"])
        for detail in error.errors()
    ]
    settings: ApiSettings = api_settings(request=request)
    logger.info(msg=f"{settings.validation_error_code}: {[detail.field for detail in details]}")
    return error_response(
        status_code=HTTPStatus.UNPROCESSABLE_CONTENT,
        error=ErrorDetail(
            code=settings.validation_error_code, message=settings.validation_error_message, details=details
        ),
    )


async def http_error_handler(request: Request, error: HTTPException) -> Response:
    code: str = HTTPStatus(value=error.status_code).name.lower()
    logger.info(msg=f"{code}: {request.method} {request.url.path}")
    response: Response = error_response(
        status_code=error.status_code, error=ErrorDetail(code=code, message=str(error.detail))
    )
    response.headers.update(error.headers or {})
    return response
