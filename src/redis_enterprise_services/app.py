import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.exceptions import HTTPException
from starlette.types import ExceptionHandler

from redis_enterprise_services.api import database_routes, health, operation_routes
from redis_enterprise_services.api.error_handlers import (
    ValidationErrorHandler,
    http_error_handler,
    project_error_handler,
)
from redis_enterprise_services.api.middleware.unexpected_errors import UnexpectedErrorMiddleware
from redis_enterprise_services.composition.services import Services
from redis_enterprise_services.config.api_settings import ApiSettings
from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.logger.configuration import configure_logging
from redis_enterprise_services.telemetry.setup import Telemetry


def create_app() -> FastAPI:
    settings: Settings = load_settings()
    configure_logging(settings=settings.log)
    app: FastAPI = FastAPI(title=settings.telemetry.service_name, lifespan=lifespan)
    services: Services = Services(settings=settings)
    app.state.settings = settings
    app.state.services = services
    app.state.database_creation = services.database_creation
    app.state.operations = services.operations
    add_error_handling(app=app, settings=settings.api)
    app.include_router(router=health.router)
    app.include_router(router=database_routes.router)
    app.include_router(router=operation_routes.router)
    FastAPIInstrumentor.instrument_app(app=app)
    return app


def add_error_handling(*, app: FastAPI, settings: ApiSettings) -> None:
    app.add_middleware(middleware_class=UnexpectedErrorMiddleware, settings=settings)
    app.add_exception_handler(
        exc_class_or_status_code=RedisEnterpriseServicesError,
        handler=cast(ExceptionHandler, project_error_handler),
    )
    app.add_exception_handler(
        exc_class_or_status_code=RequestValidationError,
        handler=cast(ExceptionHandler, ValidationErrorHandler(settings=settings)),
    )
    app.add_exception_handler(
        exc_class_or_status_code=HTTPException, handler=cast(ExceptionHandler, http_error_handler)
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings: Settings = app.state.settings
    services: Services = app.state.services
    telemetry: Telemetry = Telemetry(settings=settings.telemetry)
    telemetry.start()
    try:
        services.heartbeat.start()
        services.sweep.start()
        yield
    finally:
        await asyncio.to_thread(services.sweep.stop)
        await asyncio.to_thread(services.runner.shutdown)
        await asyncio.to_thread(services.heartbeat.stop)
        telemetry.shutdown()
