from pydantic import BaseModel

from redis_enterprise_services.operations.operation import Operation


class Admission(BaseModel):
    operation: Operation
    repeated: bool
