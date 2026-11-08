from enum import StrEnum
from typing import Protocol

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class FailureCategory(StrEnum):
    TRANSIENT = "transient"
    REJECTED = "rejected"
    UNKNOWN = "unknown"
    REQUIRES_MANUAL_INTERVENTION = "requires_manual_intervention"


class FailureClassifier(Protocol):
    def classify_step_error(self, *, error: RedisEnterpriseServicesError) -> FailureCategory: ...

    def classify_find_outcome_error(self, *, error: RedisEnterpriseServicesError) -> FailureCategory: ...
