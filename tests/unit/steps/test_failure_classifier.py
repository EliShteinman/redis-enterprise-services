import pytest

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
    UnrestorableFieldsError,
    UpdateOutcomeUnclearError,
)
from redis_enterprise_services.exceptions.edge import (
    EdgeOutcomeUnknownError,
    EdgeRequestNotSentError,
    InvalidClusterResponseError,
    InvalidEdgeRequestError,
)
from redis_enterprise_services.saga.contract.failure import FailureCategory
from redis_enterprise_services.steps.failure_classifier import ClusterFailureClassifier

CLASSIFIER: ClusterFailureClassifier = ClusterFailureClassifier(transient_error_codes=frozenset({"busy"}))


@pytest.mark.parametrize(
    argnames=("error", "expected"),
    argvalues=[
        (
            ClusterRejectedRequestError(message="m", cluster_status_code=409, cluster_error_code="busy"),
            FailureCategory.TRANSIENT,
        ),
        (
            ClusterRejectedRequestError(message="m", cluster_status_code=400, cluster_error_code="invalid"),
            FailureCategory.REJECTED,
        ),
        (InvalidEdgeRequestError(message="m"), FailureCategory.REJECTED),
        (ClusterActionFailedError(message="m"), FailureCategory.REJECTED),
        (DatabaseCreationFailedError(message="m"), FailureCategory.REJECTED),
        (DuplicateResourceNameError(message="m"), FailureCategory.REQUIRES_MANUAL_INTERVENTION),
        (UpdateOutcomeUnclearError(message="m"), FailureCategory.REQUIRES_MANUAL_INTERVENTION),
        (UnrestorableFieldsError(message="m"), FailureCategory.REJECTED),
        (EdgeRequestNotSentError(message="m"), FailureCategory.UNKNOWN),
        (EdgeOutcomeUnknownError(message="m"), FailureCategory.UNKNOWN),
        (InvalidClusterResponseError(message="m", cluster_status_code=200), FailureCategory.UNKNOWN),
        (ClusterActionTimeoutError(message="m"), FailureCategory.UNKNOWN),
        (DatabaseActivationTimeoutError(message="m"), FailureCategory.UNKNOWN),
        (DatabaseDeletionTimeoutError(message="m"), FailureCategory.UNKNOWN),
        (UnreadableClusterResponseError(message="m"), FailureCategory.UNKNOWN),
    ],
)
def test_a_step_error_gets_its_failure_category(
    error: RedisEnterpriseServicesError, expected: FailureCategory
) -> None:
    assert CLASSIFIER.classify_step_error(error=error) is expected


@pytest.mark.parametrize(
    argnames=("error", "expected"),
    argvalues=[
        (DuplicateResourceNameError(message="m"), FailureCategory.REQUIRES_MANUAL_INTERVENTION),
        (UpdateOutcomeUnclearError(message="m"), FailureCategory.REQUIRES_MANUAL_INTERVENTION),
        (ClusterActionFailedError(message="m"), FailureCategory.REJECTED),
        (DatabaseCreationFailedError(message="m"), FailureCategory.REJECTED),
        (EdgeOutcomeUnknownError(message="m"), FailureCategory.UNKNOWN),
    ],
)
def test_a_find_outcome_error_gets_its_failure_category(
    error: RedisEnterpriseServicesError, expected: FailureCategory
) -> None:
    assert CLASSIFIER.classify_find_outcome_error(error=error) is expected
