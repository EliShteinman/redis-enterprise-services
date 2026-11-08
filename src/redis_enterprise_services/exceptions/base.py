from http import HTTPStatus
from typing import ClassVar


class RedisEnterpriseServicesError(Exception):
    code: ClassVar[str] = "internal_error"
    status_code: ClassVar[int] = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(self, *, message: str) -> None:
        super().__init__(message)
        self.message: str = message

    def remote_code(self) -> str | None:
        return None

    def describe(self) -> str:
        return f"{self.code}: {self.message}"
