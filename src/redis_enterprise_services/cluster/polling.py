import time
from collections.abc import Callable

from redis_enterprise_services.config.wait_settings import WaitSettings


def poll_until(*, wait: WaitSettings, is_done: Callable[[], bool]) -> bool:
    deadline: float = time.monotonic() + wait.timeout_seconds
    while time.monotonic() < deadline:
        if is_done():
            return True
        time.sleep(wait.interval_seconds)
    return False
