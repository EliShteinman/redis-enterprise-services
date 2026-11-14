import pytest

from redis_enterprise_services.saga.contract.failure import FailureCategory
from redis_enterprise_services.saga.engine.step_runner import NextAfterFailure, next_after_failure


@pytest.mark.parametrize(
    argnames=("failure", "had_unknown_outcome", "has_result", "expected"),
    argvalues=[
        (
            FailureCategory.REQUIRES_MANUAL_INTERVENTION,
            False,
            False,
            NextAfterFailure.REQUIRES_MANUAL_INTERVENTION,
        ),
        (FailureCategory.TRANSIENT, True, False, NextAfterFailure.REQUIRES_MANUAL_INTERVENTION),
        (FailureCategory.FAILED, False, False, NextAfterFailure.FAILED),
        (FailureCategory.TRANSIENT, False, False, NextAfterFailure.RETRY),
        (FailureCategory.OUTCOME_UNKNOWN, False, False, NextAfterFailure.FIND_OUTCOME),
        (FailureCategory.FAILED, False, True, NextAfterFailure.FIND_OUTCOME),
    ],
)
def test_a_failed_attempt_leads_to_the_next_move_of_the_retry_rule(
    failure: FailureCategory, had_unknown_outcome: bool, has_result: bool, expected: NextAfterFailure
) -> None:
    assert (
        next_after_failure(failure=failure, had_unknown_outcome=had_unknown_outcome, has_result=has_result)
        is expected
    )
