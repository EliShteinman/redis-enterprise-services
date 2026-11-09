from string import Formatter


def template_placeholders(*, template: str) -> frozenset[str]:
    return frozenset(field for _, field, _, _ in Formatter().parse(template) if field is not None)
