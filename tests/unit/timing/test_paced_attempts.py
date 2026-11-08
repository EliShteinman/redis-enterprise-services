from unittest.mock import MagicMock, call, create_autospec

from redis_enterprise_services.timing.paced_attempts import paced_attempts
from redis_enterprise_services.timing.sleeper import Sleeper


def test_the_wait_grows_between_attempts_and_none_follows_the_last() -> None:
    sleeper: MagicMock = create_autospec(spec=Sleeper, instance=True)

    attempts: list[int] = list(paced_attempts(attempts=3, backoff_step_seconds=2.0, sleeper=sleeper))

    assert (attempts, sleeper.sleep.call_args_list) == ([1, 2, 3], [call(seconds=2.0), call(seconds=4.0)])
