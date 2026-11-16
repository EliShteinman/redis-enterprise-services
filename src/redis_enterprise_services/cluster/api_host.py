from urllib.parse import urlsplit

from redis_enterprise_services.exceptions.configuration import ConfigurationError


def api_host_of(*, api_url: str) -> str:
    hostname: str | None = urlsplit(api_url).hostname
    if not hostname:
        raise ConfigurationError(message=f"the cluster API URL {api_url} has no host")
    return hostname
