from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from redis_enterprise_services.api.app_state_dependencies import operation_store
from redis_enterprise_services.api.rejected_operation import OPERATION_ROUTE_REJECTIONS
from redis_enterprise_services.api.trace_id_path import checked_trace_id
from redis_enterprise_services.api.traceparent_header import require_traceparent
from redis_enterprise_services.exceptions.operation import OperationNotFoundError
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_store import OperationStore

router: APIRouter = APIRouter(
    dependencies=[Depends(dependency=require_traceparent)], responses=OPERATION_ROUTE_REJECTIONS
)


@router.get(path="/v1/operations/{trace_id}", response_model=Operation)
def get_operation(
    trace_id: Annotated[str, Depends(dependency=checked_trace_id)],
    store: Annotated[OperationStore, Depends(dependency=operation_store)],
) -> JSONResponse:
    operation: Operation | None = store.find(trace_id=trace_id)
    if operation is None:
        raise OperationNotFoundError(message=f"operation {trace_id} is not known")
    return JSONResponse(content=operation.model_dump(mode="json"))
