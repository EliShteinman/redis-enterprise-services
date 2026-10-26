import base64
import json
import logging

import httpx
from pydantic import JsonValue

from redis_enterprise_services.config.edge_settings import (
    EdgeErrorCodeSettings,
    EdgeHeaderSettings,
    EdgeSettings,
    NetworkSettings,
)
from redis_enterprise_services.edge.models import ClusterRequest, ClusterResponse
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.exceptions.edge import (
    EdgeError,
    InvalidEdgeRequestError,
    OutcomeUnknownError,
    RequestNotSentError,
    ResponseRejectedError,
)

TEXT_ENCODING: str = "utf-8"

logger: logging.Logger = logging.getLogger(name=__name__)


def basic_authorization(*, username: str, password: str) -> str:
    token: str = base64.b64encode(f"{username}:{password}".encode(TEXT_ENCODING)).decode(TEXT_ENCODING)
    return f"Basic {token}"


class EdgeClient:
    def __init__(self, *, settings: EdgeSettings, http_client: httpx.Client) -> None:
        self._settings: EdgeSettings = settings
        self._http_client: httpx.Client = http_client

    def send(self, *, network: str, request: ClusterRequest) -> ClusterResponse:
        endpoint: NetworkSettings = self._network(name=network)
        logger.debug(msg=f"{request.method} {request.url} through {network}")
        try:
            response: httpx.Response = self._http_client.post(
                url=endpoint.url,
                headers=self._headers(request=request, endpoint=endpoint),
                content=self._content(request=request),
                timeout=self._settings.timeout_seconds,
            )
        except (httpx.ConnectError, httpx.ConnectTimeout) as error:
            raise RequestNotSentError(message=f"the relay of {network} is unreachable: {error}") from error
        except httpx.TransportError as error:
            raise OutcomeUnknownError(message=f"no answer from the relay of {network}: {error}") from error
        return self._cluster_response(response=response)

    def _network(self, *, name: str) -> NetworkSettings:
        endpoint: NetworkSettings | None = self._settings.networks.get(name)
        if endpoint is None:
            raise ConfigurationError(message=f"no relay is configured for network {name}")
        return endpoint

    def _headers(self, *, request: ClusterRequest, endpoint: NetworkSettings) -> dict[str, str]:
        names: EdgeHeaderSettings = self._settings.headers
        headers: dict[str, str] = {
            names.method: request.method,
            names.url: request.url,
            names.authorization: basic_authorization(
                username=request.credentials.username,
                password=request.credentials.password.get_secret_value(),
            ),
            names.content_type: self._settings.content_type,
        }
        optional: dict[str, int | str | None] = {
            names.cluster_state_id: request.cluster_state_id,
            names.task_id: request.task_id,
            names.result_ttl: request.result_ttl,
        }
        headers |= {name: str(value) for name, value in optional.items() if value is not None}
        if endpoint.firewall is not None:
            headers[endpoint.firewall.header] = basic_authorization(
                username=endpoint.firewall.username, password=endpoint.firewall.password.get_secret_value()
            )
        return headers

    @staticmethod
    def _content(*, request: ClusterRequest) -> bytes | None:
        if request.body is None:
            return None
        return json.dumps(obj=request.body).encode(TEXT_ENCODING)

    def _cluster_response(self, *, response: httpx.Response) -> ClusterResponse:
        edge_error: str | None = response.headers.get(self._settings.headers.error)
        if edge_error is not None:
            raise self._edge_error(code=edge_error, response=response)
        return ClusterResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=self._body(response=response),
        )

    def _edge_error(self, *, code: str, response: httpx.Response) -> EdgeError:
        codes: EdgeErrorCodeSettings = self._settings.error_codes
        message: str = f"relay answered {response.status_code} {code}: {response.text}"
        logger.warning(msg=message)
        if code == codes.invalid_request:
            return InvalidEdgeRequestError(message=message)
        if code == codes.connection_failed:
            return RequestNotSentError(message=message)
        if code == codes.response_rejected:
            cluster_status: str | None = response.headers.get(self._settings.headers.cluster_status)
            return ResponseRejectedError(
                message=message, cluster_status_code=int(cluster_status) if cluster_status else None
            )
        return OutcomeUnknownError(message=message)

    @staticmethod
    def _body(*, response: httpx.Response) -> JsonValue | None:
        if not response.content:
            return None
        try:
            return response.json()
        except json.JSONDecodeError:
            return response.text
