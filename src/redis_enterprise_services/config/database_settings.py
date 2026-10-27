from pydantic import BaseModel

from redis_enterprise_services.config.wait_settings import WaitSettings


class DatabaseSettings(BaseModel):
    path: str
    active_status: str
    wait: WaitSettings
