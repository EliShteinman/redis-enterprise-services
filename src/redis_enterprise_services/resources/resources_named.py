from redis_enterprise_services.resources.models import NamedResource


def resources_named[TResource: NamedResource](*, resources: list[TResource], name: str) -> list[TResource]:
    return [resource for resource in resources if resource.name == name]
