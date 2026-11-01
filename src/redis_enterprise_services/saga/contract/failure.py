from enum import StrEnum
from typing import Protocol

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError


class Failure(StrEnum):
    TRANSIENT = "transient"
    FAILED = "failed"
    UNKNOWN = "unknown"
    MANUAL = "manual"


class FailureClassifier(Protocol):
    def classify(self, *, error: RedisEnterpriseServicesError) -> Failure: ...

    def classify_lookup(self, *, error: RedisEnterpriseServicesError) -> Failure: ...
