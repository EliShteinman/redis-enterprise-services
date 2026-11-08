from pydantic import PositiveInt

from redis_enterprise_services.config.config_model import ConfigModel


class BackgroundSettings(ConfigModel):
    max_workers: PositiveInt
