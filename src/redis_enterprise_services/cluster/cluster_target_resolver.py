import logging
from typing import Protocol

from redis_enterprise_services.cluster.models import ClusterAddress, ClusterTarget
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.exceptions.configuration import ConfigurationError

logger: logging.Logger = logging.getLogger(name=__name__)


class ClusterTargetResolver(Protocol):
    def target_for(self, *, address: ClusterAddress) -> ClusterTarget: ...


class ConfiguredCredentialsTargetResolver(ClusterTargetResolver):
    def __init__(self, *, credentials_by_api_url: dict[str, ClusterCredentials]) -> None:
        self._credentials_by_api_url: dict[str, ClusterCredentials] = credentials_by_api_url

    def target_for(self, *, address: ClusterAddress) -> ClusterTarget:
        credentials: ClusterCredentials | None = self._credentials_by_api_url.get(address.api_url)
        if credentials is None:
            message: str = f"cluster {address.api_url} is not in the cluster file, so it has no credentials"
            logger.error(msg=message)
            raise ConfigurationError(message=message)
        return ClusterTarget(network=address.network, api_url=address.api_url, credentials=credentials)
