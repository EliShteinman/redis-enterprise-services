import re

from pydantic import PositiveInt

from redis_enterprise_services.config.config_model import ConfigModel


class NameRulesSettings(ConfigModel):
    pattern: re.Pattern[str]
    max_length: PositiveInt


class RedisNameRulesSettings(ConfigModel):
    database: NameRulesSettings
    user: NameRulesSettings
    acl_and_role: NameRulesSettings


class NamingSettings(ConfigModel):
    database: NameRulesSettings
    redis: RedisNameRulesSettings
