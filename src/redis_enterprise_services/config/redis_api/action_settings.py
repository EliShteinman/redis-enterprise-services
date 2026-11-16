from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.redis_api.wait_settings import WaitSettings
from redis_enterprise_services.config.validation.item_path import ItemPath


class ActionSettings(ConfigModel):
    item_path: ItemPath
    completed_status: str
    failed_statuses: frozenset[str]
    wait: WaitSettings
