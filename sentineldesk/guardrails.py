"""Input guardrails: validation, normalization, PII masking, and threat screening."""

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from functools import partial

from langdetect import DetectorFactory, LangDetectException, detect_langs

from sentineldesk.config import SUPPORTED_LANGUAGES
from sentineldesk.schemas import Attachment, ScreeningResult, Ticket

DetectorFactory.seed = 0  # langdetect is random unless seeded

MAX_SUBJECT_CHARACTERS = 500
MAX_BODY_CHARACTERS = 20_000
MAX_ATTACHMENTS = 3
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_TOTAL_ATTACHMENT_BYTES = 20 * 1024 * 1024
_ZERO_WIDTH_CHARACTERS = "\u200b\u200c\u200d\u2060\ufeff"
_ALLOWED_ATTACHMENT_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "video/mp4",
    "video/quicktime",
}


@dataclass(frozen=True)
class TicketInputIssue:
    """A stable, safe-to-display input validation result."""

    code: str
    message: str


# langdetect is reliable on full sentences but guesses wildly on short ticket text
# ("cant login" reads as French), so short text is settled by common words first.
_LONG_TEXT_WORDS = 12
_LANGUAGE_HINTS: dict[str, set[str]] = {
    "en": {
        "the", "and", "is", "are", "not", "we", "our", "my", "i", "it", "to", "on",
        "of", "please", "since", "with", "for", "this", "after", "when", "help",
        "can", "cannot", "cant", "can't", "dont", "don't", "doesnt", "doesn't",
        "wont", "won't", "working", "keeps",
    },
    "de": {
        "und", "der", "die", "das", "nicht", "ist", "ich", "wir", "bitte", "seit",
        "mein", "meine", "mit", "für", "auf", "ein", "eine", "kann", "geht", "kein",
        "keine", "zu", "wird", "haben", "sich", "unser", "unsere", "hilfe",
        "funktioniert", "startet", "vergessen",
    },
}  # fmt: skip

# Order matters: card and account numbers are masked before the looser phone pattern.
_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("IP_ADDRESS", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    (
        "IBAN",
        re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,3})?\b"),
    ),
    ("CARD_NUMBER", re.compile(r"\b(?:\d[ -]?){12,15}\d\b")),
    (
        "ACCOUNT_NUMBER",
        re.compile(
            r"\b(?:account|acct|konto)(?:\s*(?:no\.?|number|nr\.?|nummer))?[\s:#]*\d{6,}\b",
            re.IGNORECASE,
        ),
    ),
    ("PHONE", re.compile(r"(?<![\w.])\+?\d[\d\s()/-]{7,}\d\b")),
]

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        (
            r"\b(?:ignore|disregard|forget)\b.{0,30}\b(?:previous|prior|above|earlier|all)\b"
            r".{0,20}\b(?:instructions|rules|prompts?)\b"
        ),
        (
            r"\b(?:reveal|show|print|repeat)\b.{0,20}"
            r"\b(?:system prompt|hidden instructions|your instructions)\b"
        ),
        r"\byou are now\b",
        r"\b(?:developer|jailbreak|dan) mode\b",
        (
            r"\b(?:approve|mark|close|resolve)\b.{0,30}"
            r"\b(?:automatically|without review|as resolved|as low priority)\b"
        ),
        (
            r"\b(?:ignoriere|vergiss|missachte)\b.{0,30}\b(?:vorherigen|bisherigen|alle|obigen)\b"
            r".{0,20}\b(?:anweisungen|regeln|befehle)\b"
        ),
        r"\b(?:zeige|verrate|gib)\b.{0,20}\b(?:systemprompt|system-prompt|anweisungen)\b",
    )
]


def normalize_untrusted_text(text: str) -> str:
    """Canonicalize customer-controlled text before detection or prompting.

    NFKC folds compatibility characters, while removing zero-width characters
    prevents simple obfuscations such as ``ign\u200bore`` from bypassing pattern
    matching. Newlines are retained so ticket formatting remains readable.
    """
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.translate(
        {ord(character): None for character in _ZERO_WIDTH_CHARACTERS}
    )
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[^\S\n]+", " ", normalized)
    normalized = re.sub(r" *\n *", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def validate_ticket_input(ticket: Ticket) -> list[TicketInputIssue]:
    """Return deterministic validation issues before any model work begins."""
    issues: list[TicketInputIssue] = []
    if len(ticket.subject) > MAX_SUBJECT_CHARACTERS:
        issues.append(
            TicketInputIssue(
                code="SUBJECT_TOO_LONG",
                message=(
                    "Ticket subject exceeds the "
                    f"{MAX_SUBJECT_CHARACTERS}-character limit."
                ),
            )
        )
    if len(ticket.body) > MAX_BODY_CHARACTERS:
        issues.append(
            TicketInputIssue(
                code="BODY_TOO_LONG",
                message=f"Ticket body exceeds the {MAX_BODY_CHARACTERS}-character limit.",
            )
        )
    # Avoid normalizing an arbitrarily large payload merely to decide whether it
    # is blank; the size errors above are sufficient to reject it.
    if not issues and not normalize_untrusted_text(ticket.text):
        issues.append(
            TicketInputIssue(
                code="EMPTY_TICKET",
                message="Enter a ticket subject or body before submitting.",
            )
        )
    return issues


def validate_attachments(
    attachments: Sequence[Attachment],
) -> list[TicketInputIssue]:
    """Validate attachment count, bytes, declared type, and file signature."""
    issues: list[TicketInputIssue] = []
    if len(attachments) > MAX_ATTACHMENTS:
        issues.append(
            TicketInputIssue(
                code="TOO_MANY_ATTACHMENTS",
                message=f"A ticket may contain at most {MAX_ATTACHMENTS} attachments.",
            )
        )
    if (
        sum(len(attachment.data) for attachment in attachments)
        > MAX_TOTAL_ATTACHMENT_BYTES
    ):
        issues.append(
            TicketInputIssue(
                code="ATTACHMENTS_TOTAL_TOO_LARGE",
                message="The combined attachment size exceeds the 20 MB limit.",
            )
        )
    for attachment in attachments:
        if not attachment.data or len(attachment.data) > MAX_ATTACHMENT_BYTES:
            issues.append(
                TicketInputIssue(
                    code="ATTACHMENT_SIZE_INVALID",
                    message="Each attachment must be nonempty and no larger than 10 MB.",
                )
            )
        if attachment.mime_type not in _ALLOWED_ATTACHMENT_MIME_TYPES:
            issues.append(
                TicketInputIssue(
                    code="UNSUPPORTED_ATTACHMENT_TYPE",
                    message="An attachment has an unsupported media type.",
                )
            )
        elif not _matches_file_signature(attachment):
            issues.append(
                TicketInputIssue(
                    code="ATTACHMENT_SIGNATURE_MISMATCH",
                    message="An attachment's content does not match its media type.",
                )
            )
    # Multiple attachments can trigger the same stable code; report it once.
    return list({issue.code: issue for issue in issues}.values())


def _matches_file_signature(attachment: Attachment) -> bool:
    data = attachment.data
    if attachment.mime_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if attachment.mime_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if attachment.mime_type == "image/webp":
        return data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    if attachment.mime_type in {"video/mp4", "video/quicktime"}:
        return len(data) >= 12 and data[4:8] == b"ftyp"
    return False


def detect_language(text: str) -> str:
    """Return an ISO language code such as "en" or "de", or "unknown"."""
    text = normalize_untrusted_text(text)
    words = re.findall(r"[a-zäöüß']+", text.lower())
    if not words:
        return "unknown"
    try:
        top_guess = detect_langs(text)[0]
        detected, confidence = top_guess.lang, top_guess.prob
    except LangDetectException:
        detected, confidence = "unknown", 0.0
    if len(words) > _LONG_TEXT_WORDS and confidence >= 0.8:
        return detected

    hint_counts = {
        language: len(set(words) & hints) for language, hints in _LANGUAGE_HINTS.items()
    }
    if hint_counts["en"] != hint_counts["de"]:
        return max(hint_counts, key=lambda language: hint_counts[language])
    return detected


def find_pii(text: str) -> list[tuple[str, str]]:
    """Return (label, matched text) for each piece of personal data found."""
    text = normalize_untrusted_text(text)
    return [
        (label, match.group())
        for label, pattern in _PII_PATTERNS
        for match in pattern.finditer(text)
        if _looks_like_pii(label, match.group())
    ]


def mask_pii(text: str) -> tuple[str, dict[str, int]]:
    """Replace personal data with placeholders such as [EMAIL]. Returns text and counts."""
    text = normalize_untrusted_text(text)
    counts: Counter[str] = Counter()

    def placeholder(label: str, match: re.Match[str]) -> str:
        if not _looks_like_pii(label, match.group()):
            return match.group()
        counts[label] += 1
        return f"[{label}]"

    for label, pattern in _PII_PATTERNS:
        text = pattern.sub(partial(placeholder, label), text)
    return text, dict(counts)


def _looks_like_pii(label: str, value: str) -> bool:
    # A phone number needs at least 9 digits. Shorter runs are usually dates or IDs.
    return label != "PHONE" or sum(character.isdigit() for character in value) >= 9


def find_injection_signals(text: str) -> list[str]:
    """Return the suspicious phrases found in the text (empty when clean)."""
    text = normalize_untrusted_text(text)
    return [
        match.group()
        for pattern in _INJECTION_PATTERNS
        if (match := pattern.search(text))
    ]


def screen_ticket(ticket: Ticket) -> ScreeningResult:
    """Run every input guardrail before the ticket reaches a model."""
    normalized_subject = normalize_untrusted_text(ticket.subject)
    normalized_body = normalize_untrusted_text(ticket.body)
    normalized_text = "\n".join(
        part for part in (normalized_subject, normalized_body) if part
    )
    language = detect_language(normalized_text)
    masked_subject, subject_counts = mask_pii(normalized_subject)
    masked_body, body_counts = mask_pii(normalized_body)
    return ScreeningResult(
        language=language,
        language_supported=language in SUPPORTED_LANGUAGES,
        masked_subject=masked_subject,
        masked_body=masked_body,
        pii_counts=dict(Counter(subject_counts) + Counter(body_counts)),
        injection_signals=find_injection_signals(normalized_text),
    )
