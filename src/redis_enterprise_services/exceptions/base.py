from typing import ClassVar

from fastapi import status


class RedisEnterpriseServicesError(Exception):
    code: ClassVar[str] = "internal_error"
    status_code: ClassVar[int] = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, *, message: str) -> None:
        super().__init__(message)
        self.message: str = message
