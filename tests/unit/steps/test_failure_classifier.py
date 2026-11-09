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
    EdgeConnectionFailedError,
    EdgeOutcomeUnknownError,
    EdgeRejectedRequestError,
    EdgeRejectedResponseError,
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
            FailureCategory.FAILED,
        ),
        (
            ClusterRejectedRequestError(message="m", cluster_status_code=503, cluster_error_code=None),
            FailureCategory.FAILED,
        ),
        (EdgeRejectedRequestError(message="m"), FailureCategory.FAILED),
        (ClusterActionFailedError(message="m"), FailureCategory.FAILED),
        (DatabaseCreationFailedError(message="m"), FailureCategory.FAILED),
        (DuplicateResourceNameError(message="m"), FailureCategory.REQUIRES_MANUAL_INTERVENTION),
        (UpdateOutcomeUnclearError(message="m"), FailureCategory.REQUIRES_MANUAL_INTERVENTION),
        (UnrestorableFieldsError(message="m"), FailureCategory.FAILED),
        (EdgeConnectionFailedError(message="m"), FailureCategory.OUTCOME_UNKNOWN),
        (EdgeOutcomeUnknownError(message="m"), FailureCategory.OUTCOME_UNKNOWN),
        (EdgeRejectedResponseError(message="m", cluster_status_code=200), FailureCategory.OUTCOME_UNKNOWN),
        (ClusterActionTimeoutError(message="m"), FailureCategory.OUTCOME_UNKNOWN),
        (DatabaseActivationTimeoutError(message="m"), FailureCategory.OUTCOME_UNKNOWN),
        (DatabaseDeletionTimeoutError(message="m"), FailureCategory.OUTCOME_UNKNOWN),
        (UnreadableClusterResponseError(message="m"), FailureCategory.OUTCOME_UNKNOWN),
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
        (ClusterActionFailedError(message="m"), FailureCategory.FAILED),
        (DatabaseCreationFailedError(message="m"), FailureCategory.FAILED),
        (EdgeOutcomeUnknownError(message="m"), FailureCategory.OUTCOME_UNKNOWN),
    ],
)
def test_a_find_outcome_error_gets_its_failure_category(
    error: RedisEnterpriseServicesError, expected: FailureCategory
) -> None:
    assert CLASSIFIER.classify_find_outcome_error(error=error) is expected
