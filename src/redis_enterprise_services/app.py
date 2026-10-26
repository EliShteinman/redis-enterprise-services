from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.exceptions import HTTPException

from redis_enterprise_services.api import health
from redis_enterprise_services.api.error_handlers import (
    http_error_handler,
    project_error_handler,
    validation_error_handler,
)
from redis_enterprise_services.api.middleware.unexpected_errors import UnexpectedErrorMiddleware
from redis_enterprise_services.config.settings import Settings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.logger.configuration import configure_logging
from redis_enterprise_services.telemetry.setup import Telemetry


def create_app() -> FastAPI:
    app: FastAPI = FastAPI(title="redis-enterprise-services", lifespan=lifespan)
    app.state.settings = Settings()
    app.add_middleware(middleware_class=UnexpectedErrorMiddleware)
    app.add_exception_handler(
        exc_class_or_status_code=RedisEnterpriseServicesError, handler=project_error_handler
    )
    app.add_exception_handler(
        exc_class_or_status_code=RequestValidationError, handler=validation_error_handler
    )
    app.add_exception_handler(exc_class_or_status_code=HTTPException, handler=http_error_handler)
    app.include_router(router=health.router)
    FastAPIInstrumentor.instrument_app(app=app)
    return app


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    telemetry: Telemetry = Telemetry(settings=settings.telemetry)
    telemetry.start()
    configure_logging(settings=settings.log)
    yield
    telemetry.shutdown()
