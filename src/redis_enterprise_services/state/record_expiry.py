KEEP_OPEN_WITHOUT_EXPIRY: int = 0


def finished_ttl_or_keep_open(*, has_ended: bool, finished_ttl_seconds: int) -> int:
    return finished_ttl_seconds if has_ended else KEEP_OPEN_WITHOUT_EXPIRY
