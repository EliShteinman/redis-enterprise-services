from fastapi.responses import JSONResponse

from redis_enterprise_services.api.accepted_operation import AcceptedOperation
from redis_enterprise_services.api.operation_json_response import operation_json_response
from redis_enterprise_services.operations.start_once_result import StartOnceResult


def start_once_response(*, start_once_result: StartOnceResult) -> AcceptedOperation | JSONResponse:
    if start_once_result.already_existed:
        return operation_json_response(operation=start_once_result.operation)
    return AcceptedOperation.from_operation(operation=start_once_result.operation)
