from redis_enterprise_services.cluster.rejection_kind import has_transient_error_code, is_server_failure
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
from redis_enterprise_services.exceptions.edge import (
    EdgeConnectionFailedError,
    EdgeError,
    EdgeOutcomeUnknownError,
    EdgeRejectedRequestError,
)
from redis_enterprise_services.saga.contract.failure import FailureCategory, FailureClassifier

REQUIRES_MANUAL_INTERVENTION_ERRORS: tuple[type[RedisEnterpriseServicesError], ...] = (
    DuplicateResourceNameError,
    UpdateOutcomeUnclearError,
)

CLUSTER_REPORTED_FAILURE_ERRORS: tuple[type[RedisEnterpriseServicesError], ...] = (
    ClusterActionFailedError,
    DatabaseCreationFailedError,
)

FAILED_ERRORS: tuple[type[RedisEnterpriseServicesError], ...] = (
    EdgeRejectedRequestError,
    *CLUSTER_REPORTED_FAILURE_ERRORS,
)

TRANSIENT_LOOKUP_EDGE_ERRORS: tuple[type[RedisEnterpriseServicesError], ...] = (
    EdgeConnectionFailedError,
    EdgeOutcomeUnknownError,
)

OUTCOME_UNKNOWN_ERRORS: tuple[type[RedisEnterpriseServicesError], ...] = (
    EdgeError,
    ClusterActionTimeoutError,
    DatabaseActivationTimeoutError,
    DatabaseDeletionTimeoutError,
    UnreadableClusterResponseError,
)


class ClusterFailureClassifier(FailureClassifier):
    def __init__(self, *, transient_error_codes: frozenset[str]) -> None:
        self._transient_error_codes: frozenset[str] = transient_error_codes

    def classify_step_error(self, *, error: RedisEnterpriseServicesError) -> FailureCategory:
        if isinstance(error, REQUIRES_MANUAL_INTERVENTION_ERRORS):
            return FailureCategory.REQUIRES_MANUAL_INTERVENTION
        if isinstance(error, ClusterRejectedRequestError):
            return self._classify_rejection(error=error)
        if isinstance(error, FAILED_ERRORS):
            return FailureCategory.FAILED
        if isinstance(error, OUTCOME_UNKNOWN_ERRORS):
            return FailureCategory.OUTCOME_UNKNOWN
        return FailureCategory.FAILED

    def classify_find_outcome_error(self, *, error: RedisEnterpriseServicesError) -> FailureCategory:
        if isinstance(error, REQUIRES_MANUAL_INTERVENTION_ERRORS):
            return FailureCategory.REQUIRES_MANUAL_INTERVENTION
        if isinstance(error, CLUSTER_REPORTED_FAILURE_ERRORS):
            return FailureCategory.FAILED
        if self._is_transient_lookup_error(error=error):
            return FailureCategory.TRANSIENT
        return FailureCategory.OUTCOME_UNKNOWN

    def _is_transient_lookup_error(self, *, error: RedisEnterpriseServicesError) -> bool:
        if isinstance(error, ClusterRejectedRequestError):
            return has_transient_error_code(
                error=error, transient_error_codes=self._transient_error_codes
            ) or is_server_failure(error=error)
        return isinstance(error, TRANSIENT_LOOKUP_EDGE_ERRORS)

    def _classify_rejection(self, *, error: ClusterRejectedRequestError) -> FailureCategory:
        if has_transient_error_code(error=error, transient_error_codes=self._transient_error_codes):
            return FailureCategory.TRANSIENT
        if is_server_failure(error=error):
            return FailureCategory.OUTCOME_UNKNOWN
        return FailureCategory.FAILED
