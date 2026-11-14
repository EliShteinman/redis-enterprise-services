import re

ACL_SELECTOR_WORD: str = (
    r"(?:[+-]@[A-Za-z0-9_-]+"
    r"|[+-][A-Za-z0-9_.-]+(?:\|[A-Za-z0-9_.-]+)?"
    r"|%(?:[Rr][Ww]?|[Ww][Rr]?)~\S+"
    r"|~\S*"
    r"|&\S*"
    r"|allkeys|allcommands|nocommands|resetkeys|allchannels|resetchannels)"
)
ACL_USER_FLAG: str = r"(?:on|off)"
ACL_RULE_WORD: str = rf"(?:{ACL_SELECTOR_WORD}|{ACL_USER_FLAG})"
ACL_RULE_SELECTOR: str = rf"\(\s*{ACL_SELECTOR_WORD}(?:\s+{ACL_SELECTOR_WORD})*\s*\)"
ACL_RULE_ITEM: str = rf"(?:{ACL_RULE_WORD}|{ACL_RULE_SELECTOR})"
ACL_RULE_PATTERN: str = rf"^\s*{ACL_RULE_ITEM}(?:\s+{ACL_RULE_ITEM})*\s*$"
REDIS_MIN_PASSWORD_LENGTH: int = 8
ACL_RULE_REGEX: re.Pattern[str] = re.compile(ACL_RULE_PATTERN)


def reject_invalid_acl_rule(rule: str) -> str:
    if ACL_RULE_REGEX.fullmatch(rule) is None:
        raise ValueError("acl_rule has a word that is not part of Redis's ACL syntax, or it sets a password")
    return rule
