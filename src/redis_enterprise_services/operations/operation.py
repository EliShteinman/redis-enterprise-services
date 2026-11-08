from pydantic import BaseModel, Field

from redis_enterprise_services.operations.database_result import DatabaseResult
from redis_enterprise_services.operations.error_info import ErrorInfo
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.remaining_resource import RemainingResource


class Operation(BaseModel):
    trace_id: str = Field(
        description="The trace ID of the request that started the operation.",
        examples=["4bf92f3577b34da6a3ce929d0e0e4736"],
    )
    status: OperationStatus = Field(
        default=OperationStatus.RUNNING,
        description="running: still running. succeeded: done. rejected: refused before anything changed. "
        "rolled_back: failed, and everything was undone. requires_manual_intervention: failed, "
        "and not everything was undone (see not_rolled_back, which is missing after a crash; then the "
        "saga record is the source).",
        examples=["succeeded"],
    )
    database: DatabaseResult | None = Field(
        default=None, description="The database as it is now, when the operation succeeded. Otherwise null."
    )
    error: ErrorInfo | None = Field(
        default=None,
        exclude_if=lambda error: error is None,
        description="Why the operation failed. Only when it failed.",
    )
    not_rolled_back: list[RemainingResource] | None = Field(
        default=None,
        exclude_if=lambda not_rolled_back: not_rolled_back is None,
        description="What stayed on the clusters after a failure. Empty when everything was undone.",
    )
