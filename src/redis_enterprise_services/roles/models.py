from redis_enterprise_services.resources.spec import NamedSpec


class NewRole(NamedSpec):
    management: str
    database_uids: list[int]
