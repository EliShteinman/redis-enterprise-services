from unittest.mock import MagicMock, create_autospec

from redis import Redis

from redis_enterprise_services.state.redis_abandoned_store import RedisAbandonedStore
from redis_enterprise_services.state.redis_keys import RedisKeys


def test_an_unreadable_operation_is_skipped_and_the_others_are_still_found() -> None:
    client: MagicMock = create_autospec(spec=Redis, instance=True)
    client.smembers.return_value = {"trace-bad", "trace-good"}
    client.exists.return_value = 0

    def stored(*, name: str) -> str:
        return "{not json" if "trace-bad" in name else '{"status": "running"}'

    client.get.side_effect = stored
    store: RedisAbandonedStore = RedisAbandonedStore(
        client=client, keys=RedisKeys(key_prefix="res:", hash_tag="state"), finished_ttl_seconds=600
    )

    assert store.abandoned_candidate_trace_ids() == ["trace-good"]
