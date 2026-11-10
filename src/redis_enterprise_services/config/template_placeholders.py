from string import Formatter


def template_placeholders(*, template: str) -> frozenset[str]:
    return frozenset(field for _, field, _, _ in Formatter().parse(template) if field is not None)


def reject_placeholders_other_than(*, template: str, allowed: frozenset[str]) -> None:
    if template_placeholders(template=template) != allowed:
        raise ValueError(f"{template} must use exactly the placeholders {sorted(allowed)}")
