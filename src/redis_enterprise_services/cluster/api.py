from http import HTTPStatus

from pydantic import JsonValue

from redis_enterprise_services.edge.client import EdgeClient
from redis_enterprise_services.edge.models import ClusterRequest, ClusterResponse, ClusterTarget, HttpMethod
from redis_enterprise_services.exceptions.cluster import ClusterRequestError

ERROR_CODE_FIELD: str = "error_code"


class ClusterApi:
    def __init__(self, *, edge_client: EdgeClient) -> None:
        self._edge_client: EdgeClient = edge_client

    def send(
        self,
        *,
        target: ClusterTarget,
        method: HttpMethod,
        path: str,
        query: str | None = None,
        body: JsonValue | None = None,
        cluster_state_id: int | None = None,
    ) -> ClusterResponse:
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
            raise cluster_error(response=response)
        return response


def cluster_error(*, response: ClusterResponse) -> ClusterRequestError:
    error_code: JsonValue = response.body.get(ERROR_CODE_FIELD) if isinstance(response.body, dict) else None
    return ClusterRequestError(
        message=f"cluster answered {response.status_code}: {response.body}",
        cluster_status_code=response.status_code,
        error_code=error_code if isinstance(error_code, str) else None,
    )
