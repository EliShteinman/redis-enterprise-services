from http import HTTPStatus

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from redis_enterprise_services.api.internal_error_report import report_internal_error
from redis_enterprise_services.api.rejection_error import RejectionError
from redis_enterprise_services.api.rejection_response import rejection_response
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.operations.public_errors import PublicErrors


class UnexpectedErrorMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, public_errors: PublicErrors) -> None:
        super().__init__(app=app)
        self._public_errors: PublicErrors = public_errors

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except Exception as error:  # noqa: BLE001 - logged with its traceback by report_internal_error
            report_internal_error(error=error, message="unexpected error")
            internal_error: PublicError = self._public_errors.internal_error()
            return rejection_response(
                request=request,
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                error=RejectionError(code=internal_error.code, message=internal_error.message),
            )
