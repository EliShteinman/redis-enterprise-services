from typing import ClassVar

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class ConfigurationError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "configuration_error"
