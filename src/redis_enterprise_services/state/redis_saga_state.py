import logging

from redis import Redis
from redis.commands.core import Script

from redis_enterprise_services.saga.contract.saga_record import SETTLED_STATUSES, SagaRecord
from redis_enterprise_services.saga.contract.saga_record_store import SagaRecordReader, SagaRecordWriter
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


class RedisSagaState(SagaRecordWriter, SagaRecordReader):
    def __init__(self, *, client: Redis, keys: RedisKeys, finished_operation_ttl_seconds: int) -> None:
        self._client: Redis = client
        self._keys: RedisKeys = keys
        self._finished_ttl_seconds: int = finished_operation_ttl_seconds
        self._save_unfinished: Script = client.register_script(script=SAVE_UNFINISHED)
        self._save_finished: Script = client.register_script(script=SAVE_FINISHED)

    def save(self, *, record: SagaRecord) -> None:
        self._save_unfinished(
            keys=self._record_keys(record=record), args=[record.model_dump_json(), record.saga_id]
        )
        logger.debug(msg=f"saga {record.saga_id} saved")

    def save_final(self, *, record: SagaRecord) -> None:
        if record.status not in SETTLED_STATUSES:
            self.save(record=record)
            logger.warning(msg=f"saga {record.saga_id} stored as {record.status.value}, kept without expiry")
            return
        self._save_finished(
            keys=self._record_keys(record=record),
            args=[record.model_dump_json(), record.saga_id, self._finished_ttl_seconds],
        )
        logger.info(msg=f"saga {record.saga_id} stored as {record.status.value}")

    def find(self, *, saga_id: str) -> SagaRecord | None:
        stored: str | bytes | None = self._client.get(name=self._keys.saga(saga_id=saga_id))
        if stored is None:
            logger.warning(msg=f"saga {saga_id} is not stored")
            return None
        return SagaRecord.model_validate_json(json_data=stored)

    def _record_keys(self, *, record: SagaRecord) -> list[str]:
        return [self._keys.saga(saga_id=record.saga_id), self._keys.unfinished()]
