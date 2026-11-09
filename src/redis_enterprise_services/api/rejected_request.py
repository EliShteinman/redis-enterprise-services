from pydantic import BaseModel, Field

from redis_enterprise_services.api.rejection_error import RejectionError


class RejectedRequest(BaseModel):
    trace_id: str = Field(
        description="The trace ID of this request.", examples=["4bf92f3577b34da6a3ce929d0e0e4736"]
    )
    error: RejectionError = Field(description="Why the request was refused.")
