from pydantic import BaseModel, Field

from redis_enterprise_services.api.rejection_error import RejectionError
from redis_enterprise_services.operations.operation_status import OperationStatus


class RejectedOperation(BaseModel):
    trace_id: str = Field(
        description="The trace ID of the request.", examples=["4bf92f3577b34da6a3ce929d0e0e4736"]
    )
    status: OperationStatus = Field(
        description="Always rejected: nothing was changed.", examples=["rejected"]
    )
    database: None = Field(default=None, description="Always null.")
    error: RejectionError = Field(description="Why the request was refused.")
