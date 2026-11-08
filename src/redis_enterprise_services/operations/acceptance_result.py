from pydantic import BaseModel

from redis_enterprise_services.operations.operation import Operation


class AcceptanceResult(BaseModel):
    operation: Operation
    already_accepted: bool
