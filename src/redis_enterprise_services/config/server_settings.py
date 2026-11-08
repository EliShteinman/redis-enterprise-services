from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.port import Port


class ServerSettings(ConfigModel):
    host: str
    port: Port
