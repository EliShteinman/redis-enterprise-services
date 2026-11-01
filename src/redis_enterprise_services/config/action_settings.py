from pydantic import BaseModel

from redis_enterprise_services.config.wait_settings import WaitSettings


class ActionSettings(BaseModel):
    path: str
    completed_status: str
    failed_statuses: frozenset[str]
    wait: WaitSettings
