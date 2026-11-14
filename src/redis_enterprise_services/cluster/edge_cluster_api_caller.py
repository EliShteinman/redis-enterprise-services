import logging
from http import HTTPStatus
from urllib.parse import urlsplit, urlunsplit

from pydantic import JsonValue

from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.cluster_url import cluster_url
from redis_enterprise_services.cluster.edge_transport import EdgeTransport
from redis_enterprise_services.cluster.json_body import string_field
from redis_enterprise_services.cluster.models import ClusterTarget, SuccessfulClusterResponse
from redis_enterprise_services.cluster_access.http_method import HttpMethod
from redis_enterprise_services.config.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.edge.models import ClusterRequest, ClusterResponse
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.cluster import ClusterRejectedRequestError

logger: logging.Logger = logging.getLogger(name=__name__)


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
        crdb_task_id: str | None = None,
        result_ttl_seconds: int | None = None,
    ) -> SuccessfulClusterResponse:
        request: ClusterRequest = ClusterRequest(
            method=method,
            url=cluster_url(api_url=target.api_url, path=path, query_string=query_string),
            credentials=target.credentials,
            body=body,
            cluster_state_id=cluster_state_id,
            crdb_task_id=crdb_task_id,
            result_ttl_seconds=result_ttl_seconds,
        )
        try:
            response: ClusterResponse = self._edge_transport.send(network=target.network, request=request)
        except RedisEnterpriseServicesError as error:
            with_cluster_url(error=error, cluster_url=target.api_url)
            raise
        if is_cluster_rejection(status_code=response.status_code):
            raise with_cluster_url(
                error=cluster_rejection(
                    request=request, response=response, error_code_field=self._settings.fields.error_code
                ),
                cluster_url=target.api_url,
            )
        return SuccessfulClusterResponse(body=response.body, cluster_state_id=response.cluster_state_id)


def is_cluster_rejection(*, status_code: int) -> bool:
    return status_code >= HTTPStatus.MULTIPLE_CHOICES


def cluster_rejection(
    *, request: ClusterRequest, response: ClusterResponse, error_code_field: str
) -> ClusterRejectedRequestError:
    cluster_error_code: str | None = string_field(body=response.body, name=error_code_field)
    refused_with: str = f"was refused with status {response.status_code}"
    refusal: str = f"{request.method} {url_without_query(url=request.url)} {refused_with}"
    logger.info(msg=f"{request.method} {request.url} {refused_with}: {response.body}")
    return ClusterRejectedRequestError(
        message=refusal if cluster_error_code is None else f"{refusal} ({cluster_error_code})",
        cluster_status_code=response.status_code,
        cluster_error_code=cluster_error_code,
    )


def url_without_query(*, url: str) -> str:
    return urlunsplit(urlsplit(url)._replace(query="", fragment=""))


def with_cluster_url[TError: RedisEnterpriseServicesError](*, error: TError, cluster_url: str) -> TError:
    if error.cluster_url is None:
        error.cluster_url = cluster_url
    return error
