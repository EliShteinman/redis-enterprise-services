from unittest.mock import MagicMock, call, create_autospec

from redis_enterprise_services.config.saga_settings import RetrySettings
from redis_enterprise_services.timing.paced_attempts import paced_attempts
from redis_enterprise_services.timing.sleeper import Sleeper


def test_the_wait_grows_between_attempts_and_none_follows_the_last() -> None:
    sleeper: MagicMock = create_autospec(spec=Sleeper, instance=True)

    list(paced_attempts(retry=RetrySettings(attempts=3, backoff_step_seconds=2.0), sleeper=sleeper))

    assert sleeper.sleep.call_args_list == [call(seconds=2.0), call(seconds=4.0)]
