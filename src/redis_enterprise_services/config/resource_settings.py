from redis_enterprise_services.config.config_model import ConfigModel


class ResourceSettings(ConfigModel):
    collection_path: str
    item_path: str
    list_fields: list[str]
