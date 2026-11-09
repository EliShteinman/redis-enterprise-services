from redis import Redis

from redis_enterprise_services.config.settings import Settings
from redis_enterprise_services.state.redis_abandoned_store import RedisAbandonedStore
from redis_enterprise_services.state.redis_client import build_redis_client
from redis_enterprise_services.state.redis_heartbeat_store import RedisHeartbeatStore
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.state.redis_operation_store import RedisOperationStore
from redis_enterprise_services.state.redis_saga_lock import RedisSagaLock
from redis_enterprise_services.state.redis_saga_record_store import RedisSagaRecordStore
from redis_enterprise_services.state.tracked_record_writer import TrackedRecordWriter
from redis_enterprise_services.timing.deadline_polling import DeadlinePolling


class StateWiring:
    def __init__(self, *, settings: Settings, deadline_polling: DeadlinePolling) -> None:
        redis_client: Redis = build_redis_client(settings=settings.state)
        redis_keys: RedisKeys = RedisKeys(
            key_prefix=settings.state.key_prefix, hash_tag=settings.state.hash_tag
        )
        record_writer: TrackedRecordWriter = TrackedRecordWriter(client=redis_client)
        self.operation_store: RedisOperationStore = RedisOperationStore(
            client=redis_client,
            keys=redis_keys,
            record_writer=record_writer,
            finished_ttl_seconds=settings.state.finished_ttl_seconds,
            heartbeat_ttl_seconds=settings.liveness.heartbeat_ttl_seconds,
        )
        self.heartbeat_store: RedisHeartbeatStore = RedisHeartbeatStore(
            client=redis_client,
            keys=redis_keys,
            heartbeat_ttl_seconds=settings.liveness.heartbeat_ttl_seconds,
        )
        self.saga_lock: RedisSagaLock = RedisSagaLock(
            client=redis_client,
            keys=redis_keys,
            settings=settings.state.lock,
            deadline_polling=deadline_polling,
        )
        self.saga_record_store: RedisSagaRecordStore = RedisSagaRecordStore(
            client=redis_client,
            keys=redis_keys,
            record_writer=record_writer,
            finished_ttl_seconds=settings.state.finished_ttl_seconds,
        )
        self._redis_client: Redis = redis_client
        self.abandoned_store: RedisAbandonedStore = RedisAbandonedStore(
            client=redis_client, keys=redis_keys, finished_ttl_seconds=settings.state.finished_ttl_seconds
        )

    def close(self) -> None:
        self._redis_client.close()
