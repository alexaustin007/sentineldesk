"""Output verification: evidence grounding and security checks on a drafted reply.

A sentence is removed when it promises something no retrieved resolution contains
(money, percentages, deadlines, refunds, guarantees, legal statements) or cites a
ticket that was not retrieved. Any removal or security finding fails verification,
which sends the draft to human review.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from sentineldesk.config import SUPPORTED_LANGUAGES
from sentineldesk.guardrails import detect_language, find_injection_signals, find_pii
from sentineldesk.policy_patterns import COMMITMENT_TOPICS, NUMERIC_COMMITMENTS
from sentineldesk.schemas import Precedent

CITATION_PATTERN = re.compile(r"\[([A-Z][A-Z0-9]*-[A-Za-z0-9-]+)\]")
# A bracket listing several tickets, such as "[TKT-00001, TKT-00002]".
_CITATION_GROUP = re.compile(
    r"\[([A-Z][A-Z0-9]*-[A-Za-z0-9-]+(?:\s*[,;]\s*[A-Z][A-Z0-9]*-[A-Za-z0-9-]+)+)\]"
)
_NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)?")
# Split after . ! ? or a closing citation bracket when the next sentence starts with
# a capital letter, so "Do X. [TKT-00042] Do Y." keeps each citation with its sentence.
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?\]])\s+(?=[A-ZÄÖÜ\"'])")
_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
# Template slots from the historical answers, such as <name> or <tel_num>.
TEMPLATE_PLACEHOLDER = re.compile(r"<(?!br>)[a-z_]+>")
_LEAK_MARKERS = re.compile(
    r"system prompt|my instructions|as an ai\b|</?ticket>", re.IGNORECASE
)


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    cleaned_reply: str
    removed_claims: list[str]
    issues: list[str]


def verify_reply(
    draft: str, precedents: Sequence[Precedent], expected_language: str
) -> VerificationResult:
    """Remove unsupported sentences, then check citations, security, and language."""
    draft = split_citation_groups(draft)
    evidence_ids = {precedent.ticket_id for precedent in precedents}
    evidence_text = "\n".join(precedent.answer for precedent in precedents)
    issues: list[str] = []
    removed_claims: list[str] = []

    kept_lines = []
    for line in draft.splitlines():
        if not line.strip():
            kept_lines.append("")
            continue
        kept_sentences = []
        for sentence in _SENTENCE_BOUNDARY.split(line):
            problems = [
                *unsupported_claims(sentence, evidence_text),
                *unknown_citations(sentence, evidence_ids),
                *(
                    f"template placeholder {placeholder}"
                    for placeholder in TEMPLATE_PLACEHOLDER.findall(sentence)
                ),
            ]
            if problems:
                removed_claims.append(sentence)
                issues.append(f"Removed ({'; '.join(problems)}): {sentence}")
            else:
                kept_sentences.append(sentence)
        if kept_sentences:
            kept_lines.append(" ".join(kept_sentences))
    cleaned_reply = re.sub(r"\n{3,}", "\n\n", "\n".join(kept_lines)).strip()

    if not set(CITATION_PATTERN.findall(cleaned_reply)) & evidence_ids:
        issues.append("Reply cites no retrieved historical ticket")
    issues.extend(security_issues(cleaned_reply, evidence_text))
    reply_language = detect_language(CITATION_PATTERN.sub("", cleaned_reply))
    if expected_language in SUPPORTED_LANGUAGES and reply_language != expected_language:
        issues.append(
            f"Reply language '{reply_language}' does not match "
            f"the ticket language '{expected_language}'"
        )
    return VerificationResult(
        passed=not issues,
        cleaned_reply=cleaned_reply,
        removed_claims=removed_claims,
        issues=issues,
    )


def split_citation_groups(text: str) -> str:
    """Rewrite "[TKT-1, TKT-2]" as "[TKT-1] [TKT-2]" so every citation is checkable."""
    return _CITATION_GROUP.sub(
        lambda match: " ".join(
            f"[{ticket_id.strip()}]" for ticket_id in re.split(r"[,;]", match.group(1))
        ),
        text,
    )


def unsupported_claims(sentence: str, evidence_text: str) -> list[str]:
    """Commitments in `sentence` that the evidence does not contain."""
    problems = []
    evidence_numbers = set(_NUMBER_PATTERN.findall(evidence_text))
    for name, pattern in NUMERIC_COMMITMENTS:
        for match in pattern.finditer(sentence):
            if not set(_NUMBER_PATTERN.findall(match.group())) <= evidence_numbers:
                problems.append(f"unsupported {name} '{match.group().strip()}'")
    for topic, pattern in COMMITMENT_TOPICS:
        if pattern.search(sentence) and not pattern.search(evidence_text):
            problems.append(f"unsupported {topic}")
    return problems


def unknown_citations(sentence: str, evidence_ids: set[str]) -> list[str]:
    return [
        f"cites unretrieved ticket {cited_id}"
        for cited_id in CITATION_PATTERN.findall(sentence)
        if cited_id not in evidence_ids
    ]


def security_issues(reply: str, evidence_text: str) -> list[str]:
    """Personal data, links, or injected text that the evidence does not justify."""
    issues = [
        f"Reply contains {label.lower().replace('_', ' ')} that is not in the evidence"
        for label, value in find_pii(reply)
        if value not in evidence_text
    ]
    issues.extend(
        f"Reply contains a link that is not in the evidence: {url}"
        for url in _URL_PATTERN.findall(reply)
        if url not in evidence_text
    )
    if _LEAK_MARKERS.search(reply) or find_injection_signals(reply):
        issues.append("Reply contains prompt-injection or system-prompt text")
    return list(dict.fromkeys(issues))  # drop duplicates, keep order
