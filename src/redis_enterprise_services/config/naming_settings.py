import re

from pydantic import Field

from redis_enterprise_services.config.config_model import ConfigModel


class NameRulesSettings(ConfigModel):
    pattern: re.Pattern[str]
    max_length: int = Field(gt=0)


class NamingSettings(ConfigModel):
    database: NameRulesSettings
