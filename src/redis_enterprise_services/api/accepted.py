from pydantic import BaseModel

from redis_enterprise_services.operations.operation_status import OperationStatus


class Accepted(BaseModel):
    trace_id: str
    status: OperationStatus
