import logging

from redis import Redis
from redis.commands.core import Script

from redis_enterprise_services.saga.models import SagaRecord
from redis_enterprise_services.saga.state import SagaStateRepository
from redis_enterprise_services.state.redis_keys import RedisKeys

logger: logging.Logger = logging.getLogger(name=__name__)

SAVE_UNFINISHED: str = """
redis.call('SET', KEYS[1], ARGV[1])
redis.call('SADD', KEYS[2], ARGV[2])
return true
"""

SAVE_FINISHED: str = """
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[3])
redis.call('SREM', KEYS[2], ARGV[2])
return true
"""


class RedisSagaState(SagaStateRepository):
    def __init__(self, *, client: Redis, keys: RedisKeys, finished_ttl_seconds: int) -> None:
        self._keys: RedisKeys = keys
        self._finished_ttl_seconds: int = finished_ttl_seconds
        self._save_unfinished: Script = client.register_script(script=SAVE_UNFINISHED)
        self._save_finished: Script = client.register_script(script=SAVE_FINISHED)

    def save(self, *, record: SagaRecord) -> None:
        self._save_unfinished(
            keys=self._record_keys(record=record), args=[record.model_dump_json(), record.saga_id]
        )
        logger.debug(msg=f"saga {record.saga_id} saved")

    def finish(self, *, record: SagaRecord) -> None:
        self._save_finished(
            keys=self._record_keys(record=record),
            args=[record.model_dump_json(), record.saga_id, self._finished_ttl_seconds],
        )
        logger.info(msg=f"saga {record.saga_id} stored as {record.status.value}")

    def _record_keys(self, *, record: SagaRecord) -> list[str]:
        return [self._keys.saga(saga_id=record.saga_id), self._keys.unfinished()]
