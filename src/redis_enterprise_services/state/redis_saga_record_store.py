import logging

from redis import Redis
from redis.commands.core import Script

from redis_enterprise_services.saga.contract.saga_record import CLEANLY_ENDED_STATUSES, SagaRecord
from redis_enterprise_services.saga.contract.saga_record_store import SagaRecordReader, SagaRecordWriter
from redis_enterprise_services.state.redis_keys import RedisKeys

logger: logging.Logger = logging.getLogger(name=__name__)

SAVE_WITHOUT_EXPIRY_AND_ADD_TO_UNFINISHED_SET: str = """
redis.call('SET', KEYS[1], ARGV[1])
redis.call('SADD', KEYS[2], ARGV[2])
return true
"""

SAVE_WITH_EXPIRY_AND_REMOVE_FROM_UNFINISHED_SET: str = """
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[3])
redis.call('SREM', KEYS[2], ARGV[2])
return true
"""


class RedisSagaRecordStore(SagaRecordWriter, SagaRecordReader):
    def __init__(self, *, client: Redis, keys: RedisKeys, finished_ttl_seconds: int) -> None:
        self._client: Redis = client
        self._keys: RedisKeys = keys
        self._finished_ttl_seconds: int = finished_ttl_seconds
        self._save_without_expiry_and_add_to_unfinished_set: Script = client.register_script(
            script=SAVE_WITHOUT_EXPIRY_AND_ADD_TO_UNFINISHED_SET
        )
        self._save_with_expiry_and_remove_from_unfinished_set: Script = client.register_script(
            script=SAVE_WITH_EXPIRY_AND_REMOVE_FROM_UNFINISHED_SET
        )

    def save(self, *, record: SagaRecord) -> None:
        self._save_without_expiry_and_add_to_unfinished_set(
            keys=self._record_and_unfinished_set_keys(record=record),
            args=[record.model_dump_json(), record.saga_id],
        )
        logger.debug(msg=f"saga {record.saga_id} saved")

    def save_final(self, *, record: SagaRecord) -> None:
        if record.status not in CLEANLY_ENDED_STATUSES:
            self.save(record=record)
            logger.warning(msg=f"saga {record.saga_id} stored as {record.status.value}, kept without expiry")
            return
        self._save_with_expiry_and_remove_from_unfinished_set(
            keys=self._record_and_unfinished_set_keys(record=record),
            args=[record.model_dump_json(), record.saga_id, self._finished_ttl_seconds],
        )
        logger.info(msg=f"saga {record.saga_id} stored as {record.status.value}")

    def find(self, *, saga_id: str) -> SagaRecord | None:
        stored: str | bytes | None = self._client.get(name=self._keys.saga_record(saga_id=saga_id))
        if stored is None:
            logger.debug(msg=f"saga {saga_id} is not stored")
            return None
        return SagaRecord.model_validate_json(json_data=stored)

    def _record_and_unfinished_set_keys(self, *, record: SagaRecord) -> list[str]:
        return [self._keys.saga_record(saga_id=record.saga_id), self._keys.unfinished_saga_ids()]
