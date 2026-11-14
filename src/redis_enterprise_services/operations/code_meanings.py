from collections.abc import Mapping


def code_meanings_description[TCode: str](*, meanings: Mapping[TCode, str]) -> str:
    return ", ".join(f"{code} ({meaning})" for code, meaning in meanings.items())
