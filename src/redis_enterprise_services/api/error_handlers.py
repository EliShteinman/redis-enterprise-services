import logging
from http import HTTPStatus

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from redis_enterprise_services.api.error_response import ErrorDetail, FieldError, error_response
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError

VALIDATION_ERROR_CODE: str = "validation_error"
VALIDATION_ERROR_MESSAGE: str = "the request does not match the contract"
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
    logger.info(msg=f"{VALIDATION_ERROR_CODE}: {[detail.field for detail in details]}")
    return error_response(
        status_code=HTTPStatus.UNPROCESSABLE_CONTENT,
        error=ErrorDetail(code=VALIDATION_ERROR_CODE, message=VALIDATION_ERROR_MESSAGE, details=details),
    )


async def http_error_handler(request: Request, error: HTTPException) -> Response:
    code: str = HTTPStatus(value=error.status_code).name.lower()
    logger.info(msg=f"{code}: {request.method} {request.url.path}")
    response: Response = error_response(
        status_code=error.status_code, error=ErrorDetail(code=code, message=str(error.detail))
    )
    response.headers.update(error.headers or {})
    return response
