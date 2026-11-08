from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from redis_enterprise_services.api.accepted import Accepted
from redis_enterprise_services.api.creation_examples import CREATION_EXAMPLES
from redis_enterprise_services.api.dependencies import database_creation
from redis_enterprise_services.api.rejected_response import COMMAND_REJECTIONS
from redis_enterprise_services.api.traceparent import require_traceparent
from redis_enterprise_services.creation.creation_request import CreationRequest
from redis_enterprise_services.creation.database_creation import DatabaseCreation
from redis_enterprise_services.operations.admission import Admission
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.telemetry.trace_id import current_trace_id

router: APIRouter = APIRouter(
    dependencies=[Depends(dependency=require_traceparent)], responses=COMMAND_REJECTIONS
)


@router.post(
    path="/v1/databases/create",
    status_code=HTTPStatus.ACCEPTED,
    response_model=Accepted,
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
    request: Annotated[CreationRequest, Body(openapi_examples=CREATION_EXAMPLES)],
    creation: Annotated[DatabaseCreation, Depends(dependency=database_creation)],
) -> Accepted | JSONResponse:
    admission: Admission = creation.accept(trace_id=current_trace_id(), request=request)
    if admission.repeated:
        return JSONResponse(content=admission.operation.model_dump(mode="json"))
    return Accepted(trace_id=admission.operation.trace_id, status=admission.operation.status)
