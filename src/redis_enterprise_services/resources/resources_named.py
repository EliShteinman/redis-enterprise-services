from redis_enterprise_services.resources.models import NamedResource


def resources_named(*, resources: list[NamedResource], name: str) -> list[NamedResource]:
    return [resource for resource in resources if resource.name == name]
