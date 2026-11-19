from typing import ClassVar

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class ResourcesLockedError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "resources_locked"


class InvalidPlanError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "invalid_plan"


class MissingStepResultError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "missing_step_result"


class StepNeedsManualInterventionError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "step_needs_manual_intervention"


class MissingStepRecordError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "missing_step_record"


class UnreadableSagaRecordError(RedisEnterpriseServicesError):
    code: ClassVar[str] = "unreadable_saga_record"
