from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from redis_enterprise_services.api import health
from redis_enterprise_services.config import Settings
from redis_enterprise_services.logger import configure_logging
from redis_enterprise_services.telemetry import Telemetry


def create_app() -> FastAPI:
    app: FastAPI = FastAPI(title="redis-enterprise-services", lifespan=lifespan)
    app.state.settings = Settings()
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
