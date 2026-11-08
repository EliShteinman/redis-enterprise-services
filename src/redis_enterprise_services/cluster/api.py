from http import HTTPStatus

from pydantic import JsonValue

from redis_enterprise_services.cluster.api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.edge_transport import EdgeTransport
from redis_enterprise_services.cluster.json_body import string_field
from redis_enterprise_services.cluster.models import ClusterTarget, SuccessfulClusterResponse
from redis_enterprise_services.cluster_access.models import HttpMethod
from redis_enterprise_services.config.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.edge.models import ClusterRequest, ClusterResponse
from redis_enterprise_services.exceptions.cluster import ClusterRejectedRequestError


class ClusterApi(ClusterApiCaller):
    def __init__(self, *, transport: EdgeTransport, settings: ClusterApiSettings) -> None:
        self._transport: EdgeTransport = transport
        self._settings: ClusterApiSettings = settings

    def send(
        self,
        *,
        target: ClusterTarget,
        method: HttpMethod,
        path: str,
        query: str | None = None,
        body: JsonValue | None = None,
        cluster_state_id: int | None = None,
    ) -> SuccessfulClusterResponse:
        url: str = target.api_url + path
        request: ClusterRequest = ClusterRequest(
            method=method,
            url=f"{url}?{query}" if query else url,
            credentials=target.credentials,
            body=body,
            cluster_state_id=cluster_state_id,
        )
        response: ClusterResponse = self._transport.send(network=target.network, request=request)
        if response.status_code >= HTTPStatus.MULTIPLE_CHOICES:
            raise self._rejection_from(response=response)
        return SuccessfulClusterResponse(body=response.body, cluster_state_id=response.cluster_state_id)

    def _rejection_from(self, *, response: ClusterResponse) -> ClusterRejectedRequestError:
        return ClusterRejectedRequestError(
            message=f"cluster answered {response.status_code}: {response.body}",
            cluster_status_code=response.status_code,
            cluster_error_code=string_field(body=response.body, name=self._settings.fields.error_code),
        )
