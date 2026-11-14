from fastapi import Request
from fastapi.routing import APIRoute

COMMAND_ROUTE_TAG: str = "commands"


def is_command_request(*, request: Request) -> bool:
    route: object = request.scope.get("route")
    if not isinstance(route, APIRoute) or COMMAND_ROUTE_TAG not in route.tags:
        return False
    return request.method in (route.methods or set())
