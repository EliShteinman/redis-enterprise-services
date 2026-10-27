from redis_enterprise_services.resources.spec import NamedSpec


class NewUser(NamedSpec):
    password: str
    role_uids: list[int]
