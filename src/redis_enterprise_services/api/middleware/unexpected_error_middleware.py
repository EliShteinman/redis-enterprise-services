from http import HTTPStatus

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from redis_enterprise_services.api.rejections.internal_error_report import report_internal_error
from redis_enterprise_services.api.rejections.rejection_error import RejectionError
from redis_enterprise_services.api.rejections.rejection_response import rejection_response
from redis_enterprise_services.operations.errors.public_error import PublicError
from redis_enterprise_services.operations.errors.public_errors import PublicErrors


class UnexpectedErrorMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, public_errors: PublicErrors) -> None:
        super().__init__(app=app)
        self._public_errors: PublicErrors = public_errors

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except Exception as error:
            report_internal_error(error=error, message="unexpected error")
            unexpected_error: PublicError = self._public_errors.unexpected_error(error=error)
            return rejection_response(
                request=request,
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                error=RejectionError(
                    code=unexpected_error.code, kind=unexpected_error.kind, message=unexpected_error.message
                ),
            )
