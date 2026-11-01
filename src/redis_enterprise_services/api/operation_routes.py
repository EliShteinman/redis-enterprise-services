from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from redis_enterprise_services.api.dependencies import operation_store
from redis_enterprise_services.exceptions.operations import OperationNotFoundError
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_store import OperationStore

router: APIRouter = APIRouter()


@router.get(path="/v1/operations/{trace_id}")
def operation_status(
    trace_id: str, store: Annotated[OperationStore, Depends(dependency=operation_store)]
) -> JSONResponse:
    operation: Operation | None = store.find(trace_id=trace_id)
    if operation is None:
        raise OperationNotFoundError(message=f"operation {trace_id} is not known")
    return JSONResponse(content=operation.model_dump(mode="json"))
