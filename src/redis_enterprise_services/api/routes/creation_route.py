from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, Depends

from redis_enterprise_services.api.app_state_dependencies import database_creation_from_app_state
from redis_enterprise_services.api.rejections.rejection_openapi_responses import (
    CREATION_ROUTE_REJECTION_RESPONSES,
)
from redis_enterprise_services.api.request_examples.create_database_request_examples import (
    CREATE_DATABASE_REQUEST_EXAMPLES,
)
from redis_enterprise_services.api.routes.accepted_operation import AcceptedOperation
from redis_enterprise_services.api.routes.command_route import COMMAND_ROUTE_TAG
from redis_enterprise_services.api.tracing.traceparent_header import require_traceparent
from redis_enterprise_services.creation.database_creation import DatabaseCreation
from redis_enterprise_services.creation.requests.create_database_request import CreateDatabaseRequest
from redis_enterprise_services.telemetry.trace_id import current_trace_id

router: APIRouter = APIRouter(
    tags=[COMMAND_ROUTE_TAG],
    dependencies=[Depends(dependency=require_traceparent)],
    responses=CREATION_ROUTE_REJECTION_RESPONSES,
)


@router.post(
    path="/v1/databases/create",
    status_code=HTTPStatus.ACCEPTED,
    response_model=AcceptedOperation,
    responses={
        HTTPStatus.ACCEPTED: {
            "description": "The command is accepted and runs in the background. Its state and result "
            "are read only from GET /v1/operations/{trace_id}. One trace id means one operation: a repeat "
            "with the same trace id (the parent id and the body are not compared) starts nothing and gets "
            "the same answer."
        }
    },
)
def start_database_creation_once(
    creation_request: Annotated[
        CreateDatabaseRequest, Body(openapi_examples=CREATE_DATABASE_REQUEST_EXAMPLES)
    ],
    database_creation: Annotated[DatabaseCreation, Depends(dependency=database_creation_from_app_state)],
) -> AcceptedOperation:
    trace_id: str = current_trace_id()
    database_creation.start_once(trace_id=trace_id, creation_request=creation_request)
    return AcceptedOperation(trace_id=trace_id)
