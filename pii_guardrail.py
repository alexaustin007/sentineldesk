"""PII masking for ticket text before it reaches external LLM APIs."""

import re

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_RE = re.compile(
    r"(?<!\d)"
    r"(?:\+?\d{1,3}[\s\-.]?)?"
    r"(?:\(?\d{2,4}\)?[\s\-.]?)"
    r"\d{3,4}[\s\-.]?\d{3,4}"
    r"(?!\d)"
)
_IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)
_ACCOUNT_RE = re.compile(r"\b(?:ACCT|ACC|account)[#:\s\-]*\d{4,}\b", re.IGNORECASE)
_CREDIT_CARD_RE = re.compile(r"\b(?:\d{4}[\s\-]?){3}\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_IBAN_RE = re.compile(
    r"\b[A-Z]{2}\d{2}[\s]?[\dA-Z]{4}[\s]?(?:[\dA-Z]{4}[\s]?){2,7}[\dA-Z]{1,4}\b"
)

_PATTERNS: list[tuple[re.Pattern, str]] = [
    (_EMAIL_RE, "[EMAIL]"),
    (_SSN_RE, "[SSN]"),
    (_CREDIT_CARD_RE, "[CARD]"),
    (_IBAN_RE, "[IBAN]"),
    (_IPV4_RE, "[IP]"),
    (_ACCOUNT_RE, "[ACCOUNT]"),
    (_PHONE_RE, "[PHONE]"),
]


def mask_pii(text: str) -> str:
    """Replace emails, phones, IPs, account numbers, cards, and SSNs with placeholders."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
