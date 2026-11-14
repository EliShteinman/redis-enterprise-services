class RedisKeys:
    def __init__(self, *, key_prefix: str) -> None:
        self._key_prefix: str = key_prefix

    def saga_record(self, *, saga_id: str) -> str:
        return f"{self._key_prefix}saga:{saga_id}"

    def unfinished_saga_ids(self) -> str:
        return f"{self._key_prefix}sagas:unfinished"

    def operation(self, *, trace_id: str) -> str:
        return f"{self._key_prefix}operation:{trace_id}"

    def heartbeat(self, *, trace_id: str) -> str:
        return f"{self._key_prefix}heartbeat:{trace_id}"

    def open_trace_ids(self) -> str:
        return f"{self._key_prefix}operations:open"

    def lock(self, *, lock_key: str) -> str:
        return f"{self._key_prefix}lock:{lock_key}"

    def held_locks(self, *, owner: str) -> str:
        return f"{self._key_prefix}locks:{owner}"
