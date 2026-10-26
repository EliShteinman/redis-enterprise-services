from fastapi import FastAPI

from redis_enterprise_services.api import health


def create_app() -> FastAPI:
    app: FastAPI = FastAPI(title="redis-enterprise-services")
    app.include_router(router=health.router)
    return app
