from http import HTTPStatus

from pydantic import JsonValue

from redis_enterprise_services.cluster.caller import ClusterCaller
from redis_enterprise_services.cluster.json_body import string_field
from redis_enterprise_services.cluster.models import ClusterAnswer, ClusterTarget
from redis_enterprise_services.cluster.transport import EdgeTransport
from redis_enterprise_services.config.cluster_settings import ClusterSettings
from redis_enterprise_services.edge.models import ClusterRequest, ClusterResponse, HttpMethod
from redis_enterprise_services.exceptions.cluster import ClusterRequestError


class ClusterApi(ClusterCaller):
    def __init__(self, *, edge_client: EdgeTransport, settings: ClusterSettings) -> None:
        self._edge_client: EdgeTransport = edge_client
        self._settings: ClusterSettings = settings

    def send(
        self,
        *,
        target: ClusterTarget,
        method: HttpMethod,
        path: str,
        query: str | None = None,
        body: JsonValue | None = None,
        cluster_state_id: int | None = None,
    ) -> ClusterAnswer:
        url: str = target.api_url + path
        request: ClusterRequest = ClusterRequest(
            method=method,
            url=f"{url}?{query}" if query else url,
            credentials=target.credentials,
            body=body,
            cluster_state_id=cluster_state_id,
        )
        response: ClusterResponse = self._edge_client.send(network=target.network, request=request)
        if response.status_code >= HTTPStatus.BAD_REQUEST:
            raise self._cluster_error(response=response)
        return ClusterAnswer(body=response.body, cluster_state_id=response.cluster_state_id)

    def _cluster_error(self, *, response: ClusterResponse) -> ClusterRequestError:
        return ClusterRequestError(
            message=f"cluster answered {response.status_code}: {response.body}",
            cluster_status_code=response.status_code,
            error_code=string_field(body=response.body, name=self._settings.fields.error_code),
        )
