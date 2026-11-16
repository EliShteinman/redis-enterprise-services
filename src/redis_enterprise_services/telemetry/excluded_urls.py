import re


def excluded_urls(*, paths: frozenset[str]) -> str:
    return ",".join(f"^[a-z]+://[^/]+{re.escape(path)}$" for path in sorted(paths))
