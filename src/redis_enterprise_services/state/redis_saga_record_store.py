import logging

from redis import Redis

from redis_enterprise_services.saga.contract.saga_record import SagaRecord
from redis_enterprise_services.saga.contract.saga_record_store import SagaRecordReader, SagaRecordWriter
from redis_enterprise_services.state.record_expiry import KEEP_OPEN_WITHOUT_EXPIRY, finished_ttl_or_keep_open
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.state.tracked_record_writer import TrackedRecordWriter

logger: logging.Logger = logging.getLogger(name=__name__)


class RedisSagaRecordStore(SagaRecordWriter, SagaRecordReader):
    def __init__(
        self, *, client: Redis, keys: RedisKeys, record_writer: TrackedRecordWriter, finished_ttl_seconds: int
    ) -> None:
        self._client: Redis = client
        self._keys: RedisKeys = keys
        self._record_writer: TrackedRecordWriter = record_writer
        self._finished_ttl_seconds: int = finished_ttl_seconds

    def save(self, *, record: SagaRecord) -> None:
        self._write(record=record, ttl_seconds=KEEP_OPEN_WITHOUT_EXPIRY)
        logger.debug(msg=f"saga {record.saga_id} saved")

    def save_final(self, *, record: SagaRecord) -> None:
        ended_cleanly: bool = record.has_ended_cleanly()
        self._write(
            record=record,
            ttl_seconds=finished_ttl_or_keep_open(
                has_ended_cleanly=ended_cleanly, finished_ttl_seconds=self._finished_ttl_seconds
            ),
        )
        log_final_save(record=record, ended_cleanly=ended_cleanly)

    def find(self, *, saga_id: str) -> SagaRecord | None:
        stored: str | bytes | None = self._client.get(name=self._keys.saga_record(saga_id=saga_id))
        if stored is None:
            logger.warning(msg=f"saga {saga_id} is not stored")
            return None
        return SagaRecord.model_validate_json(json_data=stored)

    def _write(self, *, record: SagaRecord, ttl_seconds: int) -> None:
        self._record_writer.save(
            record_key=self._keys.saga_record(saga_id=record.saga_id),
            tracking_set_key=self._keys.unfinished_saga_ids(),
            member=record.saga_id,
            record_json=record.model_dump_json(),
            ttl_seconds=ttl_seconds,
        )


def log_final_save(*, record: SagaRecord, ended_cleanly: bool) -> None:
    if ended_cleanly:
        logger.info(msg=f"saga {record.saga_id} stored as {record.status.value}")
        return
    logger.warning(msg=f"saga {record.saga_id} stored as {record.status.value}, kept without expiry")
