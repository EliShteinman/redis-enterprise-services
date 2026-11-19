from pydantic import JsonValue

from redis_enterprise_services.config.config_model import ConfigModel


class DatabaseDefaultsSettings(ConfigModel):
    database: dict[str, JsonValue]
    persistence_values: dict[str, dict[str, JsonValue]]
    sharding_values: dict[str, JsonValue]
