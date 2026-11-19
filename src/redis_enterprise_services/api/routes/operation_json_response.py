from fastapi.responses import JSONResponse

from redis_enterprise_services.operations.operation import Operation


def operation_json_response(*, operation: Operation) -> JSONResponse:
    return JSONResponse(content=operation.model_dump(mode="json", serialize_as_any=True))
