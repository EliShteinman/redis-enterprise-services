from pydantic import BaseModel, Field

from redis_enterprise_services.operations.operation_status import OperationStatus


class Accepted(BaseModel):
    trace_id: str = Field(
        description="The trace ID from the traceparent header. Ask for the result with it. "
        "One trace ID is one operation, so start a new trace for each command.",
        examples=["4bf92f3577b34da6a3ce929d0e0e4736"],
    )
    status: OperationStatus = Field(
        description="Always running: the operation runs in the background.", examples=["running"]
    )
