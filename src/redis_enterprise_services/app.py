from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.exceptions import HTTPException
from starlette.types import ExceptionHandler

from redis_enterprise_services.api import health
from redis_enterprise_services.api.error_handlers import (
    ValidationErrorHandler,
    http_error_handler,
    project_error_handler,
)
from redis_enterprise_services.api.middleware.unexpected_errors import UnexpectedErrorMiddleware
from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.logger.configuration import configure_logging
from redis_enterprise_services.telemetry.setup import Telemetry


def create_app() -> FastAPI:
    settings: Settings = load_settings()
    app: FastAPI = FastAPI(title=settings.telemetry.service_name, lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(middleware_class=UnexpectedErrorMiddleware, settings=settings.api)
    app.add_exception_handler(
        exc_class_or_status_code=RedisEnterpriseServicesError,
        handler=cast("ExceptionHandler", project_error_handler),
    )
    app.add_exception_handler(
        exc_class_or_status_code=RequestValidationError,
        handler=cast("ExceptionHandler", ValidationErrorHandler(settings=settings.api)),
    )
    app.add_exception_handler(
        exc_class_or_status_code=HTTPException, handler=cast("ExceptionHandler", http_error_handler)
    )
    app.include_router(router=health.router)
    FastAPIInstrumentor.instrument_app(app=app)
    return app


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings: Settings = app.state.settings
    telemetry: Telemetry = Telemetry(settings=settings.telemetry)
    telemetry.start()
    configure_logging(settings=settings.log)
    yield
    telemetry.shutdown()
