class RedisKeys:
    def __init__(self, *, prefix: str, hash_tag: str) -> None:
        self._prefix: str = f"{prefix}{{{hash_tag}}}"

    def saga(self, *, saga_id: str) -> str:
        return f"{self._prefix}saga:{saga_id}"

    def unfinished(self) -> str:
        return f"{self._prefix}sagas:unfinished"

    def lock(self, *, key: str) -> str:
        return f"{self._prefix}lock:{key}"
