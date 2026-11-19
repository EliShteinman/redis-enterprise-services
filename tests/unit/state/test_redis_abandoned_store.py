import pytest

from redis_enterprise_services.state.redis_abandoned_store import is_running_or_unrecorded


@pytest.mark.parametrize(
    argnames=("stored_json", "candidate"),
    argvalues=[
        (None, True),
        ('{"status": "running"}', True),
        ('{"status": "succeeded"}', False),
        ("{not json", False),
        ('["running"]', False),
    ],
)
def test_only_a_running_or_unrecorded_operation_is_an_abandoned_candidate(
    stored_json: str | None, candidate: bool
) -> None:
    assert is_running_or_unrecorded(trace_id="trace-1", stored_json=stored_json) is candidate
