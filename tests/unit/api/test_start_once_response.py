from fastapi.responses import JSONResponse

from redis_enterprise_services.api.accepted_operation import AcceptedOperation
from redis_enterprise_services.api.start_once_response import start_once_response
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.start_once_result import StartOnceResult

OPERATION: Operation = Operation(trace_id="trace-1")


def test_an_operation_that_already_existed_is_answered_as_it_is_stored() -> None:
    response: AcceptedOperation | JSONResponse = start_once_response(
        start_once_result=StartOnceResult(operation=OPERATION, already_existed=True)
    )

    assert isinstance(response, JSONResponse) and response.status_code == 200


def test_a_new_operation_is_answered_as_accepted() -> None:
    response: AcceptedOperation | JSONResponse = start_once_response(
        start_once_result=StartOnceResult(operation=OPERATION, already_existed=False)
    )

    assert response == AcceptedOperation(trace_id="trace-1", status=OPERATION.status)
