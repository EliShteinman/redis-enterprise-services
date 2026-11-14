from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


def with_cluster_url[TError: RedisEnterpriseServicesError](*, error: TError, cluster_url: str) -> TError:
    if error.cluster_url is None:
        error.cluster_url = cluster_url
    return error
