class RedisKeys:
    def __init__(self, *, key_prefix: str, hash_tag: str) -> None:
        self._tagged_prefix: str = f"{key_prefix}{{{hash_tag}}}"

    def saga_record(self, *, saga_id: str) -> str:
        return f"{self._tagged_prefix}saga:{saga_id}"

    def unfinished_saga_ids(self) -> str:
        return f"{self._tagged_prefix}sagas:unfinished"

    def operation(self, *, trace_id: str) -> str:
        return f"{self._tagged_prefix}operation:{trace_id}"

    def heartbeat(self, *, trace_id: str) -> str:
        return f"{self._tagged_prefix}heartbeat:{trace_id}"

    def open_trace_ids(self) -> str:
        return f"{self._tagged_prefix}operations:open"

    def lock(self, *, lock_key: str) -> str:
        return f"{self._tagged_prefix}lock:{lock_key}"

    def held_locks(self, *, owner: str) -> str:
        return f"{self._tagged_prefix}locks:{owner}"
