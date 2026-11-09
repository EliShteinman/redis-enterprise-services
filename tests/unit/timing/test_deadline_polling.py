from redis_enterprise_services.timing.deadline_polling import next_wait_seconds


def test_the_last_wait_ends_at_the_deadline_so_one_last_poll_happens_there() -> None:
    assert next_wait_seconds(now=8.0, deadline=10.0, poll_interval_seconds=4.0) == 2.0


def test_no_wait_is_left_at_the_deadline() -> None:
    assert next_wait_seconds(now=10.0, deadline=10.0, poll_interval_seconds=4.0) is None
