from urllib.parse import urlencode

from redis_enterprise_services.config.cluster_settings import FieldsQuerySettings


def fields_query(*, settings: FieldsQuerySettings, fields: list[str]) -> str:
    return urlencode(query={settings.name: settings.separator.join(fields)}, safe=settings.separator)
