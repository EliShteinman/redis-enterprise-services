ACL_RULE_WORD: str = (
    r"(?:[+-]@[A-Za-z0-9_-]+"
    r"|[+-][A-Za-z0-9_.-]+(?:\|[A-Za-z0-9_.-]+)?"
    r"|%(?:R|W|RW)?~\S*"
    r"|~\S*"
    r"|&\S*"
    r"|allkeys|allcommands|nocommands|resetkeys|allchannels|resetchannels|on|off)"
)
ACL_RULE_SELECTOR: str = rf"\(\s*{ACL_RULE_WORD}(?:\s+{ACL_RULE_WORD})*\s*\)"
ACL_RULE_ITEM: str = rf"(?:{ACL_RULE_WORD}|{ACL_RULE_SELECTOR})"
ACL_RULE_PATTERN: str = rf"^\s*{ACL_RULE_ITEM}(?:\s+{ACL_RULE_ITEM})*\s*$"
REDIS_MIN_PASSWORD_LENGTH: int = 8
