from pydantic import BaseModel, Field

from redis_enterprise_services.operations.database_result import DatabaseResult
from redis_enterprise_services.operations.operation_error import OperationError
from redis_enterprise_services.operations.operation_status import OperationStatus


class Operation(BaseModel):
    trace_id: str
    status: OperationStatus = OperationStatus.RUNNING
    database: DatabaseResult | None = None
    error: OperationError | None = Field(default=None, exclude_if=lambda error: error is None)
