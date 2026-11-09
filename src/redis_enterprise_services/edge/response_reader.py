import logging

import requests
from pydantic import JsonValue
from requests.structures import CaseInsensitiveDict

from redis_enterprise_services.config.edge_settings import EdgeErrorCodeSettings, EdgeSettings
from redis_enterprise_services.edge.models import ClusterResponse
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.edge import (
    EdgeConnectionFailedError,
    EdgeOutcomeUnknownError,
    EdgeRejectedRequestError,
    EdgeRejectedResponseError,
)

logger: logging.Logger = logging.getLogger(name=__name__)


def optional_int_header(*, headers: CaseInsensitiveDict[str], name: str) -> int | None:
    value: str | None = headers.get(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        logger.warning(msg=f"header {name} is not a number, it is ignored: {value!r}")
        return None


class EdgeResponseReader:
    def __init__(self, *, settings: EdgeSettings) -> None:
        self._settings: EdgeSettings = settings

    def unwrap_cluster_response(self, *, relay_response: requests.Response) -> ClusterResponse:
        edge_error_code: str | None = relay_response.headers.get(self._settings.headers.edge_error_code)
        if edge_error_code is not None:
            error: RedisEnterpriseServicesError = self._error_for_edge_error_code(
                edge_error_code=edge_error_code, relay_response=relay_response
            )
            logger.warning(msg=error.message)
            raise error
        return ClusterResponse(
            status_code=relay_response.status_code,
            headers=dict(relay_response.headers),
            body=self._decoded_body(relay_response=relay_response),
            cluster_state_id=optional_int_header(
                headers=relay_response.headers, name=self._settings.headers.cluster_state_id
            ),
        )

    def _error_for_edge_error_code(
        self, *, edge_error_code: str, relay_response: requests.Response
    ) -> RedisEnterpriseServicesError:
        message: str = f"relay answered {relay_response.status_code} {edge_error_code}: {relay_response.text}"
        error_type: type[RedisEnterpriseServicesError] = edge_error_type_for(
            edge_error_code=edge_error_code, codes=self._settings.error_codes
        )
        if error_type is EdgeRejectedResponseError:
            return EdgeRejectedResponseError(
                message=message,
                cluster_status_code=optional_int_header(
                    headers=relay_response.headers, name=self._settings.headers.cluster_status_code
                ),
            )
        return error_type(message=message)

    @staticmethod
    def _decoded_body(*, relay_response: requests.Response) -> JsonValue | None:
        if not relay_response.content:
            return None
        try:
            return relay_response.json()
        except requests.JSONDecodeError as error:
            message: str = (
                f"answered {relay_response.status_code} with a body that is not JSON and no edge error code"
            )
            logger.warning(msg=message)
            raise EdgeOutcomeUnknownError(message=message) from error


def edge_error_type_for(
    *, edge_error_code: str, codes: EdgeErrorCodeSettings
) -> type[RedisEnterpriseServicesError]:
    error_type_by_code: dict[str, type[RedisEnterpriseServicesError]] = {
        codes.invalid_request: EdgeRejectedRequestError,
        codes.connection_failed: EdgeConnectionFailedError,
        codes.response_rejected: EdgeRejectedResponseError,
    }
    return error_type_by_code.get(edge_error_code, EdgeOutcomeUnknownError)
