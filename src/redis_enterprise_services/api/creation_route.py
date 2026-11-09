from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from redis_enterprise_services.api.accepted_operation import AcceptedOperation
from redis_enterprise_services.api.app_state_dependencies import database_creation_from_app_state
from redis_enterprise_services.api.create_database_request_examples import CREATE_DATABASE_REQUEST_EXAMPLES
from redis_enterprise_services.api.rejected_operation import CREATION_ROUTE_REJECTION_RESPONSES
from redis_enterprise_services.api.traceparent_header import require_traceparent
from redis_enterprise_services.creation.create_database_request import CreateDatabaseRequest
from redis_enterprise_services.creation.database_creation import DatabaseCreation
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.start_once_result import StartOnceResult
from redis_enterprise_services.telemetry.trace_id import current_trace_id

router: APIRouter = APIRouter(
    dependencies=[Depends(dependency=require_traceparent)], responses=CREATION_ROUTE_REJECTION_RESPONSES
)


@router.post(
    path="/v1/databases/create",
    status_code=HTTPStatus.ACCEPTED,
    response_model=AcceptedOperation,
    responses={
        HTTPStatus.OK: {
            "model": Operation,
            "description": "An operation with the same trace id already exists (the parent id is not "
            "compared, nor the body): nothing new starts, and the current state of that operation is "
            "returned, as in the status query. One trace id means one operation.",
        }
    },
)
def start_database_creation_once(
    creation_request: Annotated[
        CreateDatabaseRequest, Body(openapi_examples=CREATE_DATABASE_REQUEST_EXAMPLES)
    ],
    database_creation: Annotated[DatabaseCreation, Depends(dependency=database_creation_from_app_state)],
) -> AcceptedOperation | JSONResponse:
    start_once_result: StartOnceResult = database_creation.start_once(
        trace_id=current_trace_id(), creation_request=creation_request
    )
    if start_once_result.already_existed:
        return JSONResponse(content=start_once_result.operation.model_dump(mode="json"))
    return AcceptedOperation(
        trace_id=start_once_result.operation.trace_id, status=start_once_result.operation.status
    )
