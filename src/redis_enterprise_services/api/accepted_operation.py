from pydantic import BaseModel, Field


class AcceptedOperation(BaseModel):
    trace_id: str = Field(
        description="The trace ID from the traceparent header. Read the operation's state and result with it "
        "from GET /v1/operations/{trace_id}. One trace ID is one operation, so start a new trace for each "
        "command.",
        examples=["4bf92f3577b34da6a3ce929d0e0e4736"],
    )
