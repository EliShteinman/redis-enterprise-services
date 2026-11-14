from pydantic import BaseModel

from redis_enterprise_services.operations.operation import Operation


class StartOnceResult(BaseModel):
    operation: Operation
    already_existed: bool
