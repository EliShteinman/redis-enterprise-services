from typing import ClassVar


class RedisEnterpriseServicesError(Exception):
    code: ClassVar[str]
    status_code: ClassVar[int]

    def __init__(self, *, message: str) -> None:
        super().__init__(message)
        self.message: str = message
