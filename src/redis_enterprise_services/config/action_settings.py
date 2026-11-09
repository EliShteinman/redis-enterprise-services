from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.item_path import ItemPath
from redis_enterprise_services.config.wait_settings import WaitSettings


class ActionSettings(ConfigModel):
    item_path: ItemPath
    completed_status: str
    failed_statuses: frozenset[str]
    wait: WaitSettings
