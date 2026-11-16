from redis import Redis
from redis.commands.core import Script

from redis_enterprise_services.state.record_expiry import NO_EXPIRY

TRACKED: str = "1"
NOT_TRACKED: str = "0"

SAVE_TRACKED_RECORD: str = f"""
local record_key, tracking_set_key = KEYS[1], KEYS[2]
local record_json, member, ttl_seconds, tracked = ARGV[1], ARGV[2], ARGV[3], ARGV[4]
if ttl_seconds == '{NO_EXPIRY}' then
    redis.call('SET', record_key, record_json)
else
    redis.call('SET', record_key, record_json, 'EX', ttl_seconds)
end
if tracked == '{TRACKED}' then
    redis.call('SADD', tracking_set_key, member)
else
    redis.call('SREM', tracking_set_key, member)
end
return true
"""


class TrackedRecordWriter:
    def __init__(self, *, client: Redis) -> None:
        self._save_tracked_record: Script = client.register_script(script=SAVE_TRACKED_RECORD)

    def save(
        self,
        *,
        record_key: str,
        tracking_set_key: str,
        member: str,
        record_json: str,
        ttl_seconds: int,
        is_tracked: bool,
    ) -> None:
        self._save_tracked_record(
            keys=[record_key, tracking_set_key],
            args=[record_json, member, ttl_seconds, TRACKED if is_tracked else NOT_TRACKED],
        )
