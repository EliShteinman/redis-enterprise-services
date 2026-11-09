from collections.abc import Mapping
from http import HTTPStatus

from fastapi.responses import JSONResponse

from redis_enterprise_services.operations.operation import Operation


def operation_json_response(
    *, operation: Operation, status_code: int = HTTPStatus.OK, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=operation.model_dump(mode="json", serialize_as_any=True),
        headers=headers,
    )
