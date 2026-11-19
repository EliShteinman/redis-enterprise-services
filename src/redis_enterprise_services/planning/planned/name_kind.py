from typing import Literal

type NameKind = Literal["database", "acl", "role", "user"]

NAME_KINDS: frozenset[NameKind] = frozenset({"database", "acl", "role", "user"})
