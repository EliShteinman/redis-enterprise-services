NO_EXPIRY: int = 0


def finished_ttl_or_no_expiry(*, has_ended_cleanly: bool, finished_ttl_seconds: int) -> int:
    return finished_ttl_seconds if has_ended_cleanly else NO_EXPIRY
