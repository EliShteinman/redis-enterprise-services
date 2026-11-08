from urllib.parse import urlencode

from redis_enterprise_services.config.cluster_api_settings import FieldsQuerySettings


def fields_query_string(*, settings: FieldsQuerySettings, field_names: list[str]) -> str:
    return urlencode(query={settings.name: settings.separator.join(field_names)}, safe=settings.separator)
