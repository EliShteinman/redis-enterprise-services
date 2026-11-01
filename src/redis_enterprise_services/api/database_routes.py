from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, Depends

from redis_enterprise_services.api.accepted import Accepted
from redis_enterprise_services.api.creation_examples import CREATION_EXAMPLES
from redis_enterprise_services.api.dependencies import database_creation
from redis_enterprise_services.api.rejected_response import COMMAND_REJECTIONS
from redis_enterprise_services.api.traceparent import require_traceparent
from redis_enterprise_services.creation.creation_request import CreationRequest
from redis_enterprise_services.creation.database_creation import DatabaseCreation
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.telemetry.trace_id import current_trace_id

router: APIRouter = APIRouter(
    dependencies=[Depends(dependency=require_traceparent)], responses=COMMAND_REJECTIONS
)


@router.post(path="/v1/databases/create", status_code=HTTPStatus.ACCEPTED)
def create_database(
    request: Annotated[CreationRequest, Body(openapi_examples=CREATION_EXAMPLES)],
    creation: Annotated[DatabaseCreation, Depends(dependency=database_creation)],
) -> Accepted:
    accepted: Operation = creation.accept(trace_id=current_trace_id(), request=request)
    return Accepted(trace_id=accepted.trace_id, status=accepted.status)
