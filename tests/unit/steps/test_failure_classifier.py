import pytest

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.cluster import (
    AmbiguousResourceError,
    ClusterActionFailedError,
    ClusterActionTimeoutError,
    ClusterRequestError,
    DatabaseNotActiveError,
    UnreadableAnswerError,
    UnrestorableFieldsError,
)
from redis_enterprise_services.exceptions.edge import (
    InvalidEdgeRequestError,
    OutcomeUnknownError,
    RequestNotSentError,
    ResponseRejectedError,
)
from redis_enterprise_services.saga.failure import Failure
from redis_enterprise_services.steps.failure_classifier import ClusterFailureClassifier

CLASSIFIER: ClusterFailureClassifier = ClusterFailureClassifier(transient_codes=frozenset({"busy"}))


@pytest.mark.parametrize(
    argnames=("error", "expected"),
    argvalues=[
        (ClusterRequestError(message="m", cluster_status_code=409, error_code="busy"), Failure.TRANSIENT),
        (ClusterRequestError(message="m", cluster_status_code=400, error_code="invalid"), Failure.FAILED),
        (InvalidEdgeRequestError(message="m"), Failure.FAILED),
        (ClusterActionFailedError(message="m"), Failure.FAILED),
        (AmbiguousResourceError(message="m"), Failure.MANUAL),
        (UnrestorableFieldsError(message="m"), Failure.FAILED),
        (RequestNotSentError(message="m"), Failure.UNKNOWN),
        (OutcomeUnknownError(message="m"), Failure.UNKNOWN),
        (ResponseRejectedError(message="m", cluster_status_code=200), Failure.UNKNOWN),
        (ClusterActionTimeoutError(message="m"), Failure.UNKNOWN),
        (DatabaseNotActiveError(message="m"), Failure.UNKNOWN),
        (UnreadableAnswerError(message="m"), Failure.UNKNOWN),
    ],
)
def test_a_step_error_is_sorted_by_the_engine_table(
    error: RedisEnterpriseServicesError, expected: Failure
) -> None:
    assert CLASSIFIER.classify(error=error) is expected


@pytest.mark.parametrize(
    argnames=("error", "expected"),
    argvalues=[
        (AmbiguousResourceError(message="m"), Failure.MANUAL),
        (ClusterActionFailedError(message="m"), Failure.FAILED),
        (OutcomeUnknownError(message="m"), Failure.UNKNOWN),
    ],
)
def test_a_lookup_error_is_sorted_by_the_engine_table(
    error: RedisEnterpriseServicesError, expected: Failure
) -> None:
    assert CLASSIFIER.classify_lookup(error=error) is expected
