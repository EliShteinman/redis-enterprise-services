import json

from fastapi import Request
from fastapi.routing import APIRoute

from redis_enterprise_services.api.command_route import COMMAND_ROUTE_TAG
from redis_enterprise_services.api.rejection_error import RejectionError
from redis_enterprise_services.api.rejection_response import rejection_response

ERROR: RejectionError = RejectionError(code="validation_error", message="invalid")


def endpoint() -> None: ...


COMMAND_ROUTE: APIRoute = APIRoute(
    path="/command", endpoint=endpoint, methods=["POST"], tags=[COMMAND_ROUTE_TAG]
)


def request_to(*, route: APIRoute | None, method: str) -> Request:
    return Request(scope={"type": "http", "method": method, "headers": [], "route": route})


def body_keys(*, request: Request) -> list[str]:
    return sorted(json.loads(bytes(rejection_response(request=request, status_code=422, error=ERROR).body)))


def test_a_rejected_command_is_answered_as_a_rejected_operation() -> None:
    assert body_keys(request=request_to(route=COMMAND_ROUTE, method="POST")) == [
        "database",
        "error",
        "status",
        "trace_id",
    ]


def test_any_other_rejected_request_has_no_operation_status() -> None:
    query: APIRoute = APIRoute(path="/query", endpoint=endpoint, methods=["GET"])

    assert body_keys(request=request_to(route=query, method="GET")) == ["error", "trace_id"]


def test_a_command_route_called_with_another_method_has_no_operation_status() -> None:
    assert body_keys(request=request_to(route=COMMAND_ROUTE, method="GET")) == ["error", "trace_id"]
