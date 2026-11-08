import logging

import requests

from redis_enterprise_services.config.edge_settings import EdgeNetworkSettings, EdgeSettings
from redis_enterprise_services.edge.encoding import encoded_json_body
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
        network_settings: EdgeNetworkSettings = self._network_settings_for(network=network)
        request_line: str = f"{request.method} {request.url} through {network}"
        logger.debug(msg=request_line)
        relay_response: requests.Response = self._post_to_relay(
            network=network,
            relay_url=network_settings.url,
            headers=self._header_builder.build(request=request, network_settings=network_settings),
            data=encoded_json_body(body=request.body),
            request_line=request_line,
        )
        return self._response_reader.unwrap_cluster_response(relay_response=relay_response)

    def _post_to_relay(
        self, *, network: str, relay_url: str, headers: dict[str, str], data: bytes | None, request_line: str
    ) -> requests.Response:
        try:
            return requests.post(
                url=relay_url,
                headers=headers,
                data=data,
                timeout=self._settings.request_timeout_seconds,
                allow_redirects=False,
                verify=False,  # noqa: S501
            )
        except requests.RequestException as error:
            logger.warning(msg=f"{request_line} failed: {error!r}")
            raise edge_error_for_transport_failure(network=network, error=error) from error

    def _network_settings_for(self, *, network: str) -> EdgeNetworkSettings:
        network_settings: EdgeNetworkSettings | None = self._settings.networks.get(network)
        if network_settings is None:
            raise ConfigurationError(message=f"no relay is configured for network {network}")
        return network_settings
