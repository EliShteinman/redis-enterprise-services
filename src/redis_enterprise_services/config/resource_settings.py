from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.item_path import ItemPath


class ResourceSettings(ConfigModel):
    collection_path: str
    item_path: ItemPath
    list_fields: list[str]
