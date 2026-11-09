from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.item_path import ApiPath, ItemPath


class ResourceSettings(ConfigModel):
    collection_path: ApiPath
    item_path: ItemPath
    list_fields: list[str]
    unreturned_fields: list[str]
    secret_fields: list[str]
