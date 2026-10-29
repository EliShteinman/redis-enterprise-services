from http import HTTPStatus
from typing import ClassVar

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class DatabaseLockedError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "database_locked"
    status_code: ClassVar[int] = HTTPStatus.CONFLICT


class InvalidPlanError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "invalid_plan"


class MissingResultError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "missing_step_result"
