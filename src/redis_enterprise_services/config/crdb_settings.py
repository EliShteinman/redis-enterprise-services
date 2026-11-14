from pydantic import PositiveInt

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.item_path import ApiPath, ItemPath
from redis_enterprise_services.config.wait_settings import WaitSettings


class CrdbTaskSettings(ConfigModel):
    item_path: ItemPath
    completed_status: str
    failed_statuses: frozenset[str]
    result_ttl_seconds: PositiveInt
    wait: WaitSettings


class CrdbSettings(ConfigModel):
    collection_path: ApiPath
    item_path: ItemPath
    list_field: str
    task: CrdbTaskSettings
