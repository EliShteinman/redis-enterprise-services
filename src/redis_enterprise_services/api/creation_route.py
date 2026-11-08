from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from redis_enterprise_services.api.accepted_operation import AcceptedOperation
from redis_enterprise_services.api.app_state_dependencies import database_creation
from redis_enterprise_services.api.creation_examples import CREATION_EXAMPLES
from redis_enterprise_services.api.rejected_operation import CREATION_ROUTE_REJECTIONS
from redis_enterprise_services.api.traceparent_header import require_traceparent
from redis_enterprise_services.creation.creation_request import CreationRequest
from redis_enterprise_services.creation.database_creation import DatabaseCreation
from redis_enterprise_services.operations.acceptance_result import AcceptanceResult
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.telemetry.trace_id import current_trace_id

router: APIRouter = APIRouter(
    dependencies=[Depends(dependency=require_traceparent)], responses=CREATION_ROUTE_REJECTIONS
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
def create_database(
    creation_request: Annotated[CreationRequest, Body(openapi_examples=CREATION_EXAMPLES)],
    database_creation: Annotated[DatabaseCreation, Depends(dependency=database_creation)],
) -> AcceptedOperation | JSONResponse:
    acceptance: AcceptanceResult = database_creation.accept(
        trace_id=current_trace_id(), request=creation_request
    )
    if acceptance.already_accepted:
        return JSONResponse(content=acceptance.operation.model_dump(mode="json"))
    return AcceptedOperation(trace_id=acceptance.operation.trace_id, status=acceptance.operation.status)
