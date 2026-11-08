from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.cluster import (
    ClusterActionFailedError,
    ClusterActionTimeoutError,
    ClusterRejectedRequestError,
    DatabaseActivationTimeoutError,
    DatabaseCreationFailedError,
    DatabaseDeletionTimeoutError,
    DuplicateResourceNameError,
    UnreadableClusterResponseError,
    UpdateOutcomeUnclearError,
)
from redis_enterprise_services.exceptions.edge import EdgeError, EdgeRejectedRequestError
from redis_enterprise_services.saga.contract.failure import FailureCategory, FailureClassifier

FAILED_ERRORS: tuple[type[RedisEnterpriseServicesError], ...] = (
    EdgeRejectedRequestError,
    ClusterActionFailedError,
    DatabaseCreationFailedError,
)

UNKNOWN_OUTCOME_ERRORS: tuple[type[RedisEnterpriseServicesError], ...] = (
    ClusterActionTimeoutError,
    DatabaseActivationTimeoutError,
    DatabaseDeletionTimeoutError,
    UnreadableClusterResponseError,
)


class ClusterFailureClassifier(FailureClassifier):
    def __init__(self, *, transient_error_codes: frozenset[str]) -> None:
        self._transient_error_codes: frozenset[str] = transient_error_codes

    def classify_step_error(self, *, error: RedisEnterpriseServicesError) -> FailureCategory:
        if isinstance(error, DuplicateResourceNameError | UpdateOutcomeUnclearError):
            return FailureCategory.REQUIRES_MANUAL_INTERVENTION
        if isinstance(error, ClusterRejectedRequestError):
            return (
                FailureCategory.TRANSIENT
                if error.cluster_error_code in self._transient_error_codes
                else FailureCategory.FAILED
            )
        if isinstance(error, FAILED_ERRORS):
            return FailureCategory.FAILED
        if isinstance(error, (EdgeError, *UNKNOWN_OUTCOME_ERRORS)):
            return FailureCategory.OUTCOME_UNKNOWN
        return FailureCategory.FAILED

    def classify_find_outcome_error(self, *, error: RedisEnterpriseServicesError) -> FailureCategory:
        if isinstance(error, DuplicateResourceNameError | UpdateOutcomeUnclearError):
            return FailureCategory.REQUIRES_MANUAL_INTERVENTION
        if isinstance(error, ClusterActionFailedError | DatabaseCreationFailedError):
            return FailureCategory.FAILED
        return FailureCategory.OUTCOME_UNKNOWN
