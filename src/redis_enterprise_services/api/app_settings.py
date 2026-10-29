from fastapi import Request

from redis_enterprise_services.config.api_settings import ApiSettings
from redis_enterprise_services.config.settings import Settings


def api_settings(*, request: Request) -> ApiSettings:
    settings: Settings = request.app.state.settings
    return settings.api
