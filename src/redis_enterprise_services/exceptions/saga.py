from http import HTTPStatus
from typing import ClassVar

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class ResourcesLockedError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "resources_locked"
    status_code: ClassVar[int] = HTTPStatus.CONFLICT


class InvalidPlanError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "invalid_plan"


class MissingStepResultError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "missing_step_result"
