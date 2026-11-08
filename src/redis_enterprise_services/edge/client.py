import json
import logging

import requests

from redis_enterprise_services.config.edge_settings import EdgeNetworkSettings, EdgeSettings
from redis_enterprise_services.edge.encoding import TEXT_ENCODING
from redis_enterprise_services.edge.header_builder import EdgeHeaderBuilder
from redis_enterprise_services.edge.models import ClusterRequest, ClusterResponse
from redis_enterprise_services.edge.response_reader import EdgeResponseReader
from redis_enterprise_services.edge.transport_errors import edge_error_for_transport_failure
from redis_enterprise_services.exceptions.configuration import ConfigurationError

logger: logging.Logger = logging.getLogger(name=__name__)


class EdgeClient:
    def __init__(
        self,
        *,
        settings: EdgeSettings,
        header_builder: EdgeHeaderBuilder,
        response_reader: EdgeResponseReader,
    ) -> None:
        self._settings: EdgeSettings = settings
        self._header_builder: EdgeHeaderBuilder = header_builder
        self._response_reader: EdgeResponseReader = response_reader

    def send(self, *, network: str, request: ClusterRequest) -> ClusterResponse:
        relay_settings: EdgeNetworkSettings = self._relay_settings_for(network=network)
        logger.debug(msg=f"{request.method} {request.url} through {network}")
        try:
            response: requests.Response = requests.post(
                url=relay_settings.url,
                headers=self._header_builder.build(request=request, relay_settings=relay_settings),
                data=self._encoded_body(request=request),
                timeout=self._settings.request_timeout_seconds,
                allow_redirects=False,
                verify=False,  # noqa: S501
            )
        except requests.RequestException as error:
            logger.warning(msg=f"{request.method} {request.url} through {network} failed: {error!r}")
            raise edge_error_for_transport_failure(network=network, error=error) from error
        return self._response_reader.read(response=response)

    def _relay_settings_for(self, *, network: str) -> EdgeNetworkSettings:
        relay_settings: EdgeNetworkSettings | None = self._settings.networks.get(network)
        if relay_settings is None:
            raise ConfigurationError(message=f"no relay is configured for network {network}")
        return relay_settings

    @staticmethod
    def _encoded_body(*, request: ClusterRequest) -> bytes | None:
        if request.body is None:
            return None
        return json.dumps(obj=request.body).encode(TEXT_ENCODING)
