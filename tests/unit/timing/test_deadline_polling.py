from redis_enterprise_services.timing.deadline_polling import another_poll_fits


def test_a_poll_that_would_end_exactly_at_the_deadline_does_not_fit() -> None:
    assert not another_poll_fits(now=6.0, deadline=10.0, poll_interval_seconds=4.0)
