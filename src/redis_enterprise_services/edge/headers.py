import base64

from redis_enterprise_services.config.edge_settings import EdgeHeaderSettings, EdgeSettings, NetworkSettings
from redis_enterprise_services.edge.encoding import TEXT_ENCODING
from redis_enterprise_services.edge.models import ClusterRequest


def basic_authorization(*, username: str, password: str) -> str:
    token: str = base64.b64encode(f"{username}:{password}".encode(TEXT_ENCODING)).decode(TEXT_ENCODING)
    return f"Basic {token}"


class EdgeHeaders:
    def __init__(self, *, settings: EdgeSettings) -> None:
        self._settings: EdgeSettings = settings
        self._names: EdgeHeaderSettings = settings.headers

    def build(self, *, request: ClusterRequest, endpoint: NetworkSettings) -> dict[str, str]:
        return (
            self._required(request=request)
            | self._optional(request=request)
            | self._firewall(endpoint=endpoint)
        )

    def _required(self, *, request: ClusterRequest) -> dict[str, str]:
        return {
            self._names.method: request.method,
            self._names.url: request.url,
            self._names.authorization: basic_authorization(
                username=request.credentials.username,
                password=request.credentials.password.get_secret_value(),
            ),
            self._names.content_type: self._settings.content_type,
        }

    def _optional(self, *, request: ClusterRequest) -> dict[str, str]:
        optional: dict[str, int | str | None] = {
            self._names.cluster_state_id: request.cluster_state_id,
            self._names.task_id: request.task_id,
            self._names.result_ttl: request.result_ttl,
        }
        return {name: str(value) for name, value in optional.items() if value is not None}

    @staticmethod
    def _firewall(*, endpoint: NetworkSettings) -> dict[str, str]:
        if endpoint.firewall is None:
            return {}
        return {
            endpoint.firewall.header: basic_authorization(
                username=endpoint.firewall.username, password=endpoint.firewall.password.get_secret_value()
            )
        }
