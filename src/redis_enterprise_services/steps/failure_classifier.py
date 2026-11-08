from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.cluster import (
    AmbiguousResourceError,
    ClusterActionFailedError,
    ClusterActionTimeoutError,
    ClusterRequestError,
    DatabaseCreationFailedError,
    DatabaseNotActiveError,
    DatabaseStillExistsError,
    UnreadableAnswerError,
    UpdateOutcomeUnclearError,
)
from redis_enterprise_services.exceptions.edge import EdgeError, InvalidEdgeRequestError
from redis_enterprise_services.saga.contract.failure import Failure, FailureClassifier

KNOWN_FAILURE_ERRORS: tuple[type[RedisEnterpriseServicesError], ...] = (
    InvalidEdgeRequestError,
    ClusterActionFailedError,
    DatabaseCreationFailedError,
)

UNKNOWN_OUTCOME_ERRORS: tuple[type[RedisEnterpriseServicesError], ...] = (
    ClusterActionTimeoutError,
    DatabaseNotActiveError,
    DatabaseStillExistsError,
    UnreadableAnswerError,
)


class ClusterFailureClassifier(FailureClassifier):
    def __init__(self, *, transient_codes: frozenset[str]) -> None:
        self._transient_codes: frozenset[str] = transient_codes

    def classify(self, *, error: RedisEnterpriseServicesError) -> Failure:
        if isinstance(error, AmbiguousResourceError | UpdateOutcomeUnclearError):
            return Failure.MANUAL
        if isinstance(error, ClusterRequestError):
            return Failure.TRANSIENT if error.error_code in self._transient_codes else Failure.FAILED
        if isinstance(error, KNOWN_FAILURE_ERRORS):
            return Failure.FAILED
        if isinstance(error, (EdgeError, *UNKNOWN_OUTCOME_ERRORS)):
            return Failure.UNKNOWN
        return Failure.FAILED

    def classify_lookup(self, *, error: RedisEnterpriseServicesError) -> Failure:
        if isinstance(error, AmbiguousResourceError | UpdateOutcomeUnclearError):
            return Failure.MANUAL
        if isinstance(error, ClusterActionFailedError | DatabaseCreationFailedError):
            return Failure.FAILED
        return Failure.UNKNOWN
