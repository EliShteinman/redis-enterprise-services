import logging

from fastapi import Request, Response, status
from fastapi.exceptions import RequestValidationError
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from redis_enterprise_services.api.error_response import ErrorDetail, FieldError, error_response
from redis_enterprise_services.exceptions import RedisEnterpriseServicesError

VALIDATION_ERROR_CODE: str = "validation_error"
VALIDATION_ERROR_MESSAGE: str = "the request does not match the contract"
INTERNAL_ERROR_CODE: str = "internal_error"
INTERNAL_ERROR_MESSAGE: str = "internal error"

logger: logging.Logger = logging.getLogger(name=__name__)


class ErrorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except RedisEnterpriseServicesError as error:
            logger.warning(msg=f"{error.code}: {error.message}")
            return error_response(
                status_code=error.status_code, error=ErrorDetail(code=error.code, message=error.message)
            )
        except Exception as error:
            logger.exception(msg="unexpected error")
            trace.get_current_span().record_exception(exception=error)
            return error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=ErrorDetail(code=INTERNAL_ERROR_CODE, message=INTERNAL_ERROR_MESSAGE),
            )


async def validation_error_handler(request: Request, error: RequestValidationError) -> Response:
    details: list[FieldError] = [
        FieldError(field=".".join(str(part) for part in detail["loc"]), message=detail["msg"])
        for detail in error.errors()
    ]
    logger.info(msg=f"{VALIDATION_ERROR_CODE}: {[detail.field for detail in details]}")
    return error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        error=ErrorDetail(code=VALIDATION_ERROR_CODE, message=VALIDATION_ERROR_MESSAGE, details=details),
    )
