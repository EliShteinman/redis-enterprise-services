from pydantic import BaseModel, Field

from redis_enterprise_services.operations.database_result import DatabaseResult
from redis_enterprise_services.operations.error_info import ErrorInfo
from redis_enterprise_services.operations.not_rolled_back import NotRolledBack
from redis_enterprise_services.operations.operation_status import OperationStatus


class Operation(BaseModel):
    trace_id: str
    status: OperationStatus = OperationStatus.RUNNING
    database: DatabaseResult | None = None
    error: ErrorInfo | None = Field(default=None, exclude_if=lambda error: error is None)
    not_rolled_back: list[NotRolledBack] | None = Field(
        default=None, exclude_if=lambda not_rolled_back: not_rolled_back is None
    )
