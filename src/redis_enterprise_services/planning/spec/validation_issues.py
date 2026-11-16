from pydantic import ValidationError
from pydantic_core import ErrorDetails

ISSUE_SEPARATOR: str = "; "


def issues_text(*, error: ValidationError) -> str:
    return ISSUE_SEPARATOR.join(issue_text(issue=issue) for issue in error.errors(include_input=False))


def issue_text(*, issue: ErrorDetails) -> str:
    cause: object = issue.get("ctx", {}).get("error", issue["msg"])
    location: str = ".".join(str(part) for part in issue["loc"])
    return f"{location}: {cause}" if location else f"{cause}"
