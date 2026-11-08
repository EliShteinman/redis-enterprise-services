from unittest.mock import MagicMock, create_autospec

from redis_enterprise_services.timing.clock import Clock
from redis_enterprise_services.timing.deadline_polling import DeadlinePolling
from redis_enterprise_services.timing.sleeper import Sleeper


def test_polling_gives_up_when_the_next_poll_would_end_past_the_deadline() -> None:
    clock: MagicMock = create_autospec(spec=Clock, instance=True)
    clock.monotonic_seconds.side_effect = [0.0, 0.0, 7.0]
    sleeper: MagicMock = create_autospec(spec=Sleeper, instance=True)
    polling: DeadlinePolling = DeadlinePolling(clock=clock, sleeper=sleeper)

    finished: bool = polling.poll_until(
        is_done=lambda: False, timeout_seconds=10.0, poll_interval_seconds=4.0
    )

    assert (finished, sleeper.sleep.call_count) == (False, 1)
