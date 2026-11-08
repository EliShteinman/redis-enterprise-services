from redis import Redis
from redis.commands.core import Script

SAVE_TRACKED_RECORD: str = """
local record_key, tracking_set_key = KEYS[1], KEYS[2]
local record_json, member, ttl_seconds = ARGV[1], ARGV[2], ARGV[3]
if ttl_seconds == '0' then
    redis.call('SET', record_key, record_json)
    redis.call('SADD', tracking_set_key, member)
else
    redis.call('SET', record_key, record_json, 'EX', ttl_seconds)
    redis.call('SREM', tracking_set_key, member)
end
return true
"""


class TrackedRecordWriter:
    def __init__(self, *, client: Redis) -> None:
        self._save_tracked_record: Script = client.register_script(script=SAVE_TRACKED_RECORD)

    def save(
        self, *, record_key: str, tracking_set_key: str, member: str, record_json: str, ttl_seconds: int
    ) -> None:
        self._save_tracked_record(
            keys=[record_key, tracking_set_key], args=[record_json, member, ttl_seconds]
        )
