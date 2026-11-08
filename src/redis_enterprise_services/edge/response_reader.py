import logging

import requests
from pydantic import JsonValue
from requests.structures import CaseInsensitiveDict

from redis_enterprise_services.config.edge_settings import EdgeErrorCodeSettings, EdgeSettings
from redis_enterprise_services.edge.models import ClusterResponse
from redis_enterprise_services.exceptions.edge import (
    EdgeError,
    EdgeOutcomeUnknownError,
    EdgeRequestNotSentError,
    InvalidClusterResponseError,
    InvalidEdgeRequestError,
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

    def read(self, *, response: requests.Response) -> ClusterResponse:
        edge_error_code: str | None = response.headers.get(self._settings.headers.edge_error_code)
        if edge_error_code is not None:
            raise self._edge_error_for(code=edge_error_code, response=response)
        return ClusterResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            body=self._body(response=response),
            cluster_state_id=optional_int_header(
                headers=response.headers, name=self._settings.headers.cluster_state_id
            ),
        )

    def _edge_error_for(self, *, code: str, response: requests.Response) -> EdgeError:
        codes: EdgeErrorCodeSettings = self._settings.error_codes
        message: str = f"relay answered {response.status_code} {code}: {response.text}"
        logger.warning(msg=message)
        if code == codes.response_rejected:
            return InvalidClusterResponseError(
                message=message,
                cluster_status_code=optional_int_header(
                    headers=response.headers, name=self._settings.headers.cluster_status_code
                ),
            )
        error_type_by_code: dict[str, type[EdgeError]] = {
            codes.invalid_request: InvalidEdgeRequestError,
            codes.connection_failed: EdgeRequestNotSentError,
        }
        return error_type_by_code.get(code, EdgeOutcomeUnknownError)(message=message)

    @staticmethod
    def _body(*, response: requests.Response) -> JsonValue | None:
        if not response.content:
            return None
        try:
            return response.json()
        except requests.JSONDecodeError:
            return response.text
