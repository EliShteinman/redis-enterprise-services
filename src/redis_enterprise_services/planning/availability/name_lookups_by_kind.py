from redis_enterprise_services.planning.availability.name_lookup import NameLookup
from redis_enterprise_services.planning.name_kind import NameKind


class NameLookupsByKind:
    def __init__(self, *, database: NameLookup, acl: NameLookup, role: NameLookup, user: NameLookup) -> None:
        self._by_kind: dict[NameKind, NameLookup] = {
            "database": database,
            "acl": acl,
            "role": role,
            "user": user,
        }

    def for_kind(self, *, kind: NameKind) -> NameLookup:
        return self._by_kind[kind]
