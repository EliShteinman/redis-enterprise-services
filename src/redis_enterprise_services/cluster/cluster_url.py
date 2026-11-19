def cluster_url(*, api_url: str, path: str, query_string: str | None) -> str:
    url: str = api_url + path
    return f"{url}?{query_string}" if query_string else url
