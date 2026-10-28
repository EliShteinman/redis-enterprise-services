from enum import StrEnum

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.cluster import (
    AmbiguousResourceError,
    ClusterActionFailedError,
    ClusterActionTimeoutError,
    ClusterRequestError,
    DatabaseNotActiveError,
    UnreadableAnswerError,
)
from redis_enterprise_services.exceptions.edge import EdgeError, InvalidEdgeRequestError

UNKNOWN_OUTCOME_ERRORS: tuple[type[RedisEnterpriseServicesError], ...] = (
    ClusterActionTimeoutError,
    DatabaseNotActiveError,
    UnreadableAnswerError,
)


class Failure(StrEnum):
    TRANSIENT = "transient"
    FAILED = "failed"
    UNKNOWN = "unknown"
    MANUAL = "manual"


def classify(*, error: RedisEnterpriseServicesError, transient_codes: frozenset[str]) -> Failure:
    if isinstance(error, AmbiguousResourceError):
        return Failure.MANUAL
    if isinstance(error, ClusterRequestError):
        return Failure.TRANSIENT if error.error_code in transient_codes else Failure.FAILED
    if isinstance(error, (InvalidEdgeRequestError, ClusterActionFailedError)):
        return Failure.FAILED
    if isinstance(error, (EdgeError, *UNKNOWN_OUTCOME_ERRORS)):
        return Failure.UNKNOWN
    return Failure.FAILED


def classify_lookup(*, error: RedisEnterpriseServicesError) -> Failure:
    if isinstance(error, AmbiguousResourceError):
        return Failure.MANUAL
    if isinstance(error, ClusterActionFailedError):
        return Failure.FAILED
    return Failure.UNKNOWN


def describe(*, error: RedisEnterpriseServicesError) -> str:
    return f"{error.code}: {error.message}"
