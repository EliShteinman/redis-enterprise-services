from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.wait_settings import WaitSettings


class ActionSettings(ConfigModel):
    path: str
    completed_status: str
    failed_statuses: frozenset[str]
    wait: WaitSettings
