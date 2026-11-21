"""Input guardrails: language detection, PII masking, and prompt-injection screening."""

import re
from collections import Counter
from functools import partial

from langdetect import DetectorFactory, LangDetectException, detect_langs

from sentineldesk.config import SUPPORTED_LANGUAGES
from sentineldesk.schemas import ScreeningResult, Ticket

DetectorFactory.seed = 0  # langdetect is random unless seeded

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


def detect_language(text: str) -> str:
    """Return an ISO language code such as "en" or "de", or "unknown"."""
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
    return [
        (label, match.group())
        for label, pattern in _PII_PATTERNS
        for match in pattern.finditer(text)
        if _looks_like_pii(label, match.group())
    ]


def mask_pii(text: str) -> tuple[str, dict[str, int]]:
    """Replace personal data with placeholders such as [EMAIL]. Returns text and counts."""
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
    return [
        match.group()
        for pattern in _INJECTION_PATTERNS
        if (match := pattern.search(text))
    ]


def screen_ticket(ticket: Ticket) -> ScreeningResult:
    """Run every input guardrail before the ticket reaches a model."""
    language = detect_language(ticket.text)
    masked_subject, subject_counts = mask_pii(ticket.subject)
    masked_body, body_counts = mask_pii(ticket.body)
    return ScreeningResult(
        language=language,
        language_supported=language in SUPPORTED_LANGUAGES,
        masked_subject=masked_subject,
        masked_body=masked_body,
        pii_counts=dict(Counter(subject_counts) + Counter(body_counts)),
        injection_signals=find_injection_signals(ticket.text),
    )
