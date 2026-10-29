from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


def describe(*, error: RedisEnterpriseServicesError) -> str:
    return f"{error.code}: {error.message}"
