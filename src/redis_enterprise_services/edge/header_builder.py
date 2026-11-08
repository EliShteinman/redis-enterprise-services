import base64

from redis_enterprise_services.config.edge_settings import (
    EdgeHeaderSettings,
    EdgeNetworkSettings,
    EdgeSettings,
)
from redis_enterprise_services.edge.encoding import TEXT_ENCODING
from redis_enterprise_services.edge.models import ClusterRequest


def basic_authorization(*, username: str, password: str) -> str:
    token: str = base64.b64encode(f"{username}:{password}".encode(TEXT_ENCODING)).decode(TEXT_ENCODING)
    return f"Basic {token}"


class EdgeHeaderBuilder:
    def __init__(self, *, settings: EdgeSettings) -> None:
        self._settings: EdgeSettings = settings
        self._header_names: EdgeHeaderSettings = settings.headers

    def build(self, *, request: ClusterRequest, network_settings: EdgeNetworkSettings) -> dict[str, str]:
        return (
            self._required_headers(request=request)
            | self._optional_headers(request=request)
            | self._firewall_headers(network_settings=network_settings)
        )

    def _required_headers(self, *, request: ClusterRequest) -> dict[str, str]:
        return {
            self._header_names.cluster_method: request.method,
            self._header_names.cluster_url: request.url,
            self._header_names.cluster_authorization: basic_authorization(
                username=request.credentials.username,
                password=request.credentials.password.get_secret_value(),
            ),
            self._header_names.content_type: self._settings.request_content_type,
        }

    def _optional_headers(self, *, request: ClusterRequest) -> dict[str, str]:
        optional: dict[str, int | str | None] = {
            self._header_names.cluster_state_id: request.cluster_state_id,
            self._header_names.crdb_task_id: request.crdb_task_id,
            self._header_names.result_ttl_seconds: request.result_ttl_seconds,
        }
        return {name: str(value) for name, value in optional.items() if value is not None}

    @staticmethod
    def _firewall_headers(*, network_settings: EdgeNetworkSettings) -> dict[str, str]:
        if network_settings.firewall is None:
            return {}
        return {
            network_settings.firewall.authorization_header: basic_authorization(
                username=network_settings.firewall.username,
                password=network_settings.firewall.password.get_secret_value(),
            )
        }
