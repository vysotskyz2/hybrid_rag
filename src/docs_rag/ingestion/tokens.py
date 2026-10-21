import re
from typing import Protocol

_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...


class RegexTokenCounter:
    def count(self, text: str) -> int:
        return len(_TOKEN_RE.findall(text))
