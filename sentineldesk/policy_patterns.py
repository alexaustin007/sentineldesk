"""Shared English and German patterns for risk cues and commitments."""

import re

# Cues that make a ticket riskier than its labels suggest.
RISK_SIGNALS: list[tuple[str, re.Pattern[str]]] = [
    (
        "service outage",
        re.compile(
            r"\b(?:outage|is down|are down|went down|not reachable|unreachable"
            r"|ausfall|ausgefallen|nicht erreichbar)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "security incident",
        re.compile(
            r"\b(?:breach|hacked|ransomware|malware|phishing|unauthori[sz]ed access"
            r"|sicherheitsvorfall|gehackt|datenleck)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "data loss",
        re.compile(
            r"\b(?:data loss|lost (?:all )?data|deleted data|datenverlust"
            r"|daten (?:verloren|gelöscht))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "safety-critical environment",
        re.compile(
            r"\b(?:hospital|patients?|clinic(?:ians?)?|emr|telemedicine"
            r"|krankenhaus|patienten|klinik)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "many users affected",
        re.compile(
            r"\b(?:all users|everyone|entire (?:company|team|network|organization)"
            r"|all (?:sites|locations|customers|employees)"
            r"|alle (?:nutzer|mitarbeiter|standorte|kunden))\b",
            re.IGNORECASE,
        ),
    ),
]

# Topics the helpdesk may only promise when a past resolution did the same.
COMMITMENT_TOPICS: list[tuple[str, re.Pattern[str]]] = [
    (
        "refund or compensation",
        re.compile(
            r"\b(?:refund\w*|money back|reimburs\w*|chargeback|compensat\w*"
            r"|rückerstatt\w*|erstatt\w*|entschädig\w*|gutschrift\w*|geld zurück)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "SLA or guarantee",
        re.compile(
            r"\b(?:sla|service level|guarantee\w*|garantie\w*|garantier\w*)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "legal matter",
        re.compile(
            r"\b(?:legal\w*|lawyer|lawsuit|sue|court|liabilit\w*|anwalt|klage"
            r"|rechtlich\w*|haftung)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "pricing or discount",
        re.compile(
            r"\b(?:discount\w*|pricing|price\w*|free of charge|rabatt\w*|preis\w*"
            r"|kostenlos)\b",
            re.IGNORECASE,
        ),
    ),
]

# Concrete numbers a reply might promise: money, percentages, and deadlines.
NUMERIC_COMMITMENTS: list[tuple[str, re.Pattern[str]]] = [
    (
        "money amount",
        re.compile(
            r"[$€£]\s?\d[\d.,]*"
            r"|\b\d[\d.,]*\s?(?:€|\$|£|eur\b|euros?\b|usd\b|dollars?\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "percentage",
        re.compile(r"\b\d+(?:[.,]\d+)?\s?(?:%|percent\b|prozent\b)", re.IGNORECASE),
    ),
    (
        "deadline",
        re.compile(
            r"\b(?:within|in|innerhalb von|binnen)\s+\d+"
            r"(?:\s?(?:-|–|to|bis)\s?\d+)?\s*"
            r"(?:minutes?|hours?|business days|days?|weeks?"
            r"|minuten|stunden|werktagen|tagen|wochen)\b",
            re.IGNORECASE,
        ),
    ),
]
