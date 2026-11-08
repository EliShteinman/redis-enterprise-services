from redis_enterprise_services.config.config_model import ConfigModel


class ResourceSettings(ConfigModel):
    collection_path: str
    path: str
    list_fields: list[str]


class RoleSettings(ResourceSettings):
    database_resource_type: str
