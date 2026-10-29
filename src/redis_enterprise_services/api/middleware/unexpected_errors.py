import logging

from fastapi import Request, Response
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from redis_enterprise_services.api.app_settings import api_settings
from redis_enterprise_services.api.error_response import ErrorDetail, error_response
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError

logger: logging.Logger = logging.getLogger(name=__name__)


class UnexpectedErrorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except Exception as error:
            logger.exception(msg="unexpected error")
            trace.get_current_span().record_exception(exception=error)
            return error_response(
                status_code=RedisEnterpriseServicesError.status_code,
                error=ErrorDetail(
                    code=RedisEnterpriseServicesError.code,
                    message=api_settings(request=request).internal_error_message,
                ),
            )
