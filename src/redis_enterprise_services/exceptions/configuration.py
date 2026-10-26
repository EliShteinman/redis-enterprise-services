from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class ConfigurationError(RedisEnterpriseServicesError):
    def __init__(self, *, reason: str) -> None:
        super().__init__(f"invalid configuration: {reason}")
