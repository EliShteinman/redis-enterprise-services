import json
import logging

import requests

from redis_enterprise_services.config.edge_settings import EdgeSettings, NetworkSettings
from redis_enterprise_services.edge.encoding import TEXT_ENCODING
from redis_enterprise_services.edge.headers import EdgeHeaders
from redis_enterprise_services.edge.models import ClusterRequest, ClusterResponse
from redis_enterprise_services.edge.response_reader import EdgeResponseReader
from redis_enterprise_services.edge.transport_errors import transport_error
from redis_enterprise_services.exceptions.configuration import ConfigurationError

logger: logging.Logger = logging.getLogger(name=__name__)


class EdgeClient:
    def __init__(self, *, settings: EdgeSettings, headers: EdgeHeaders, reader: EdgeResponseReader) -> None:
        self._settings: EdgeSettings = settings
        self._headers: EdgeHeaders = headers
        self._reader: EdgeResponseReader = reader

    def send(self, *, network: str, request: ClusterRequest) -> ClusterResponse:
        endpoint: NetworkSettings = self._network(name=network)
        logger.debug(msg=f"{request.method} {request.url} through {network}")
        try:
            response: requests.Response = requests.post(
                url=endpoint.url,
                headers=self._headers.build(request=request, endpoint=endpoint),
                data=self._content(request=request),
                timeout=self._settings.timeout_seconds,
                verify=False,  # noqa: S501
            )
        except requests.RequestException as error:
            logger.warning(msg=f"{request.method} {request.url} through {network} failed: {error!r}")
            raise transport_error(network=network, error=error) from error
        return self._reader.read(response=response)

    def _network(self, *, name: str) -> NetworkSettings:
        endpoint: NetworkSettings | None = self._settings.networks.get(name)
        if endpoint is None:
            raise ConfigurationError(message=f"no relay is configured for network {name}")
        return endpoint

    @staticmethod
    def _content(*, request: ClusterRequest) -> bytes | None:
        if request.body is None:
            return None
        return json.dumps(obj=request.body).encode(TEXT_ENCODING)
