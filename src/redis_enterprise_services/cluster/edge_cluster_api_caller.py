from http import HTTPStatus

from pydantic import JsonValue

from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.cluster_url import cluster_url
from redis_enterprise_services.cluster.edge_transport import EdgeTransport
from redis_enterprise_services.cluster.json_body import string_field
from redis_enterprise_services.cluster.models import ClusterTarget, SuccessfulClusterResponse
from redis_enterprise_services.cluster_access.http_method import HttpMethod
from redis_enterprise_services.config.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.edge.models import ClusterRequest, ClusterResponse
from redis_enterprise_services.exceptions.cluster import ClusterRejectedRequestError


class EdgeClusterApiCaller(ClusterApiCaller):
    def __init__(self, *, edge_transport: EdgeTransport, settings: ClusterApiSettings) -> None:
        self._edge_transport: EdgeTransport = edge_transport
        self._settings: ClusterApiSettings = settings

    def send(
        self,
        *,
        target: ClusterTarget,
        method: HttpMethod,
        path: str,
        query_string: str | None = None,
        body: JsonValue | None = None,
        cluster_state_id: int | None = None,
    ) -> SuccessfulClusterResponse:
        request: ClusterRequest = ClusterRequest(
            method=method,
            url=cluster_url(api_url=target.api_url, path=path, query_string=query_string),
            credentials=target.credentials,
            body=body,
            cluster_state_id=cluster_state_id,
        )
        response: ClusterResponse = self._edge_transport.send(network=target.network, request=request)
        if is_cluster_rejection(status_code=response.status_code):
            raise cluster_rejection(response=response, error_code_field=self._settings.fields.error_code)
        return SuccessfulClusterResponse(body=response.body, cluster_state_id=response.cluster_state_id)


def is_cluster_rejection(*, status_code: int) -> bool:
    return status_code >= HTTPStatus.MULTIPLE_CHOICES


def cluster_rejection(*, response: ClusterResponse, error_code_field: str) -> ClusterRejectedRequestError:
    return ClusterRejectedRequestError(
        message=f"cluster answered {response.status_code}: {response.body}",
        cluster_status_code=response.status_code,
        cluster_error_code=string_field(body=response.body, name=error_code_field),
    )
