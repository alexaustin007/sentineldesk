#!/usr/bin/env python3
"""SentinelDesk stress runner. Stdlib only, Python 3.10+.

Posts every ticket in stress/tickets.jsonl to POST /api/triage, checks the
response against the contract (docs/UI_WORKFLOW.md §3, §3.1) and each ticket's
`expect` block, then prints a summary and writes stress/results-<timestamp>.json.
Plan and pass/fail rules: docs/STRESS_TEST.md.

    python3 stress/run_stress.py                       # functional pass, 1 at a time
    python3 stress/run_stress.py --only injection      # one category
    python3 stress/run_stress.py --concurrency 5 --only classification
    python3 stress/run_stress.py --burst 20            # 20 requests at the same instant
    python3 stress/run_stress.py --holdout-csv data/prepared/holdout_inputs.csv
    python3 stress/run_stress.py --dry-run             # list what would be sent, send nothing

Exit code: 0 all good, 1 at least one FAIL (or WARN with --strict), 2 usage error.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, NoReturn

HERE = Path(__file__).resolve().parent

# --- Contract vocabulary (UI_WORKFLOW.md §3.1) --------------------------------
TYPE_LABELS = {"Incident", "Request", "Problem", "Change"}
PRIORITY_LABELS = {"high", "medium", "low"}
QUEUE_LABELS = {
    "Technical Support",
    "Product Support",
    "Customer Service",
    "IT Support",
    "Billing and Payments",
    "Returns and Exchanges",
    "Service Outages and Maintenance",
    "Sales and Pre-Sales",
    "Human Resources",
    "General Inquiry",
}
LANGUAGES = {"en", "de"}
STATUSES = {"auto_draft", "human_review", "escalate"}
# Reason codes are best-effort tags: the UI always renders `message`, so an
# unknown code is a WARN, never a FAIL.
REASON_CODES = {
    "HIGH_PRIORITY_INCIDENT",
    "CRITICAL_INCIDENT_RISK",
    "LOW_CONFIDENCE",
    "LOW_MARGIN",
    "LOW_SIMILARITY",
    "UNSUPPORTED_REQUEST",
    "UNSUPPORTED_LANGUAGE",
    "PROMPT_INJECTION",
    "VERIFICATION_FAILED",
    "OTHER",
    # api/ scaffold degradations (allowed, reported as WARN "degraded")
    "GENERATION_FAILED",
    "CITATION_INVALID",
    "GUARDRAILS_UNAVAILABLE",
}
DEGRADED_REASONS = {"GENERATION_FAILED", "CITATION_INVALID", "GUARDRAILS_UNAVAILABLE"}
TICKET_ID_RE = re.compile(r"^TKT-\d{5}$")
CITED_ID_RE = re.compile(r"TKT-\d+")
PLACEHOLDER_RE = re.compile(r"\[(?:EMAIL|PHONE|IBAN)\]")

# Who fixes what. Shown in the summary so each failure lands with an owner.
REASON_OWNER = {
    "HIGH_PRIORITY_INCIDENT": "classifier",
    "CRITICAL_INCIDENT_RISK": "classifier",
    "LOW_CONFIDENCE": "classifier",
    "LOW_MARGIN": "classifier",
    "LOW_SIMILARITY": "RAG",
    "UNSUPPORTED_REQUEST": "guardrails",
    "UNSUPPORTED_LANGUAGE": "guardrails",
    "PROMPT_INJECTION": "guardrails",
}
# In --burst mode only these stay FAIL; the rest was judged by the functional pass.
LOAD_FAILS = {"transport", "http-status", "error-shape", "shape", "LEAKAGE"}
GUARDED_CATEGORIES = {"injection", "unsupported", "fake_integration", "pii"}

# Tiny stopword lists for a sanity check on the draft's language (no "die":
# it is also an English word).
EN_WORDS = {
    "the",
    "and",
    "you",
    "your",
    "we",
    "to",
    "of",
    "is",
    "for",
    "please",
    "thank",
    "thanks",
    "with",
    "this",
    "have",
    "our",
    "has",
    "been",
    "that",
    "not",
    "are",
    "will",
    "can",
    "would",
    "could",
}
DE_WORDS = {
    "der",
    "das",
    "und",
    "sie",
    "ihre",
    "wir",
    "ist",
    "nicht",
    "bitte",
    "danke",
    "mit",
    "für",
    "haben",
    "eine",
    "ein",
    "zu",
    "den",
    "dem",
    "vielen",
    "ihr",
    "uns",
    "wurde",
    "werden",
    "können",
    "sich",
    "auf",
}


@dataclass
class Check:
    name: str
    severity: str  # "fail" or "warn"
    owner: str  # API / UI / classifier / RAG / guardrails / gate
    detail: str


@dataclass
class Result:
    id: str
    category: str
    http_status: int | None = None
    latency_ms: float | None = None
    transport_error: str | None = None
    error_code: str | None = None
    escalation_status: str | None = None
    reasons: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    precedent_ids: list[str] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    response: Any = None

    def fails(self) -> list[Check]:
        return [c for c in self.checks if c.severity == "fail"]

    def warns(self) -> list[Check]:
        return [c for c in self.checks if c.severity == "warn"]


# --- Loading --------------------------------------------------------------------


def usage_error(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def load_tickets(path: Path) -> list[dict[str, Any]]:
    tickets = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            t = json.loads(line)
        except json.JSONDecodeError as e:
            usage_error(f"{path}:{n}: invalid JSON ({e})")
        # `body_repeat` / `subject_repeat` keep 10k+ character cases readable.
        t["body"] = t["body"] * int(t.get("body_repeat", 1))
        if t.get("subject") is not None:
            t["subject"] = t["subject"] * int(t.get("subject_repeat", 1))
        t.setdefault("expect", {})
        tickets.append(t)
    return tickets


def load_holdout_ids(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames or "ticket_id" not in reader.fieldnames:
            usage_error(f"{path}: expected a 'ticket_id' column")
        return {row["ticket_id"].strip() for row in reader if row.get("ticket_id")}


# --- HTTP -----------------------------------------------------------------------


def post_json(
    url: str, payload: dict[str, Any], timeout: float
) -> tuple[int | None, Any, str | None, float]:
    """Returns (http_status, parsed_body_or_raw_text, transport_error, latency_ms)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    start = time.perf_counter()
    status: int | None = None
    raw = b""
    error: str | None = None
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            raw = resp.read()
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read()
    except TimeoutError:
        error = f"TIMEOUT after {timeout:g} s"
    except urllib.error.URLError as e:
        if isinstance(e.reason, (TimeoutError, socket.timeout)):
            error = f"TIMEOUT after {timeout:g} s"
        else:
            error = f"NETWORK: {e.reason}"
    except OSError as e:
        error = f"NETWORK: {type(e).__name__}: {e}"
    latency = (time.perf_counter() - start) * 1000
    if error:
        return None, None, error, latency
    text = raw.decode("utf-8", errors="replace")
    try:
        return status, json.loads(text), None, latency
    except json.JSONDecodeError:
        return status, text, None, latency


def get_health(base_url: str) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(f"{base_url}/api/health", timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - health is informational only
        return None


# --- Contract checks --------------------------------------------------------------


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_shape(r: dict[str, Any]) -> list[Check]:
    """Required fields and types from contracts/triage_response.example.json."""
    out: list[Check] = []

    def bad(path: str, why: str, owner: str = "API", severity: str = "fail") -> None:
        out.append(Check("shape", severity, owner, f"{path}: {why}"))

    if not isinstance(r.get("request_id"), str):
        bad("request_id", "missing or not a string")
    inp = r.get("input")
    if not isinstance(inp, dict):
        bad("input", "missing")
    else:
        if not isinstance(inp.get("body"), str):
            bad("input.body", "missing")
        if not isinstance(inp.get("language_detected"), str):
            bad("input.language_detected", "missing", "guardrails")
        if "language_supported" in inp and not isinstance(
            inp["language_supported"], bool
        ):
            bad("input.language_supported", "not a bool", "guardrails")
        if not isinstance(inp.get("pii_counts"), dict) and not isinstance(
            inp.get("pii_masked"), list
        ):
            bad("input.pii_counts", "missing (use {} if none)", "guardrails", "warn")
    cls = r.get("classification")
    if not isinstance(cls, dict):
        bad("classification", "missing", "classifier")
    else:
        for head in ("type", "queue", "priority"):
            h = cls.get(head)
            if not isinstance(h, dict) or not isinstance(h.get("label"), str):
                bad(f"classification.{head}.label", "missing", "classifier")
                continue
            c = h.get("confidence")
            if not _is_num(c) or not 0 <= c <= 1:
                bad(
                    f"classification.{head}.confidence", f"{c!r} not 0..1", "classifier"
                )
            if "alternatives" in h and not isinstance(h["alternatives"], list):
                bad(f"classification.{head}.alternatives", "not a list", "classifier")
    esc = r.get("escalation")
    if not isinstance(esc, dict):
        bad("escalation", "missing", "gate")
    else:
        if not isinstance(esc.get("reasons"), list):
            bad("escalation.reasons", "missing", "gate")
        else:
            for i, reason in enumerate(esc["reasons"]):
                if not isinstance(reason, dict) or not isinstance(
                    reason.get("code"), str
                ):
                    bad(f"escalation.reasons[{i}].code", "missing", "gate")
                elif (
                    not isinstance(reason.get("message"), str) or not reason["message"]
                ):
                    bad(
                        f"escalation.reasons[{i}].message",
                        "empty (UI shows it)",
                        "gate",
                    )
        th = esc.get("thresholds")
        if not isinstance(th, dict) or not all(
            _is_num(th.get(k)) for k in ("confidence", "similarity")
        ):
            bad(
                "escalation.thresholds", "needs numeric confidence + similarity", "gate"
            )
    gr = r.get("guardrails")
    if not isinstance(gr, dict):
        bad("guardrails", "missing", "guardrails")
    else:
        for k in ("prompt_injection", "unsupported_request"):
            g = gr.get(k)
            if not isinstance(g, dict) or not isinstance(g.get("flagged"), bool):
                bad(f"guardrails.{k}.flagged", "missing", "guardrails")
        if not isinstance(gr.get("citations_valid"), bool):
            bad("guardrails.citations_valid", "missing", "guardrails")
    precs = r.get("precedents")
    if not isinstance(precs, list):
        bad("precedents", "missing", "RAG")
    else:
        required = (
            "ticket_id",
            "similarity",
            "type",
            "queue",
            "priority",
            "answer_snippet",
        )
        for i, p in enumerate(precs):
            missing = [k for k in required if not isinstance(p, dict) or k not in p]
            if missing:
                bad(f"precedents[{i}]", f"missing {', '.join(missing)}", "RAG")
                continue
            # §3: language/subject may be missing until PR #5 exports them.
            soft = [k for k in ("language", "subject") if not p.get(k)]
            if soft:
                bad(
                    f"precedents[{i}]",
                    f"no {', '.join(soft)} (UI copes)",
                    "RAG",
                    "warn",
                )
            tid = p["ticket_id"]
            if not isinstance(tid, str) or not TICKET_ID_RE.match(tid):
                bad(f"precedents[{i}].ticket_id", f"{tid!r} not TKT-#####", "RAG")
            if not _is_num(p["similarity"]) or not 0 <= p["similarity"] <= 1:
                bad(
                    f"precedents[{i}].similarity",
                    f"{p['similarity']!r} not 0..1",
                    "RAG",
                )
    draft = r.get("draft", "MISSING")
    if draft == "MISSING":
        bad("draft", "key missing (use null when not generated)", "RAG")
    elif draft is not None:
        if not isinstance(draft, dict) or not isinstance(draft.get("text"), str):
            bad("draft.text", "missing", "RAG")
        elif not isinstance(draft.get("citations"), list):
            bad("draft.citations", "missing", "RAG")
        elif not isinstance(draft.get("language"), str):
            bad("draft.language", "missing", "RAG")
    lat = r.get("latency_ms")
    if not isinstance(lat, dict) or not _is_num(lat.get("total")):
        bad("latency_ms.total", "missing", "API")
    return [c for c in out if c.severity == "fail"] + [
        c for c in out if c.severity == "warn"
    ]


def check_vocabulary(r: dict[str, Any]) -> list[Check]:
    out: list[Check] = []
    cls = r["classification"]
    for head, allowed in (
        ("type", TYPE_LABELS),
        ("queue", QUEUE_LABELS),
        ("priority", PRIORITY_LABELS),
    ):
        label = cls[head]["label"]
        if label not in allowed:
            out.append(
                Check(
                    "vocabulary", "fail", "classifier", f"{head}={label!r} not in §3.1"
                )
            )
    lang = r["input"]["language_detected"]
    supported = r["input"].get("language_supported")
    if lang not in LANGUAGES and supported is not False:
        out.append(
            Check(
                "vocabulary",
                "fail",
                "guardrails",
                f"language_detected={lang!r} but language_supported={supported}",
            )
        )
    if lang in LANGUAGES and supported is False:
        out.append(
            Check("vocabulary", "warn", "guardrails", f"{lang} marked unsupported")
        )
    status = r["escalation"].get("status")
    if status not in STATUSES:
        out.append(Check("vocabulary", "fail", "gate", f"escalation.status={status!r}"))
    for reason in r["escalation"]["reasons"]:
        code = reason["code"]
        if code in DEGRADED_REASONS:
            out.append(Check("degraded", "warn", "API", f"backend degraded: {code}"))
        elif code not in REASON_CODES:
            out.append(
                Check("vocabulary", "warn", "gate", f"unknown reason code {code!r}")
            )
    return out


def reason_evident(code: str, r: dict[str, Any]) -> bool | None:
    """Does the response itself show the condition behind `code`? None = can't tell."""
    cls = r["classification"]
    th = r["escalation"]["thresholds"]
    gr = r["guardrails"]
    if code == "HIGH_PRIORITY_INCIDENT":
        return cls["type"]["label"] == "Incident" and cls["priority"]["label"] == "high"
    if code == "CRITICAL_INCIDENT_RISK":
        risk, limit = (
            cls.get("critical_incident_risk"),
            th.get("critical_incident_risk"),
        )
        return _is_num(risk) and _is_num(limit) and risk >= limit
    if code == "LOW_CONFIDENCE":
        return (
            min(cls[h]["confidence"] for h in ("type", "queue", "priority"))
            < th["confidence"]
        )
    if code == "LOW_SIMILARITY":
        top = max((p["similarity"] for p in r["precedents"]), default=0.0)
        return top < th["similarity"]
    if code == "UNSUPPORTED_REQUEST":
        return gr["unsupported_request"]["flagged"]
    if code == "PROMPT_INJECTION":
        return gr["prompt_injection"]["flagged"] or bool(gr.get("injection_signals"))
    if code == "UNSUPPORTED_LANGUAGE":
        return r["input"].get("language_supported") is False
    return None


def reason_satisfied(code: str, r: dict[str, Any]) -> bool:
    """Code present, or its condition visible (codes are best-effort tags)."""
    return code in {x["code"] for x in r["escalation"]["reasons"]} or bool(
        reason_evident(code, r)
    )


def check_gate(r: dict[str, Any]) -> list[Check]:
    """Recompute the gate from the response itself; it has to agree with itself."""
    out: list[Check] = []
    esc = r["escalation"]
    status = esc.get("status")
    codes = {x["code"] for x in esc["reasons"]}
    if status != "auto_draft" and not codes:
        out.append(Check("gate", "fail", "gate", f"status={status} with no reason"))
    if status == "auto_draft" and codes:
        out.append(
            Check("gate", "warn", "gate", f"auto_draft with reasons {sorted(codes)}")
        )
    must_block = [
        "HIGH_PRIORITY_INCIDENT",
        "CRITICAL_INCIDENT_RISK",
        "LOW_CONFIDENCE",
        "LOW_SIMILARITY",
        "UNSUPPORTED_REQUEST",
        "PROMPT_INJECTION",
        "UNSUPPORTED_LANGUAGE",
    ]
    if status == "auto_draft":
        hits = [c for c in must_block if reason_evident(c, r)]
        if hits:
            out.append(
                Check("gate", "fail", "gate", f"auto_draft although {', '.join(hits)}")
            )
    elif status == "human_review" and reason_evident("HIGH_PRIORITY_INCIDENT", r):
        out.append(
            Check(
                "gate",
                "fail",
                "gate",
                "Incident + high must page (escalate), got human_review",
            )
        )
    if status == "auto_draft" and not r.get("draft"):
        out.append(Check("gate", "fail", "RAG", "Auto-Draft Ready but draft is null"))
    for code in sorted(codes):
        if reason_evident(code, r) is False:
            out.append(
                Check(
                    "gate",
                    "warn",
                    "gate",
                    f"{code} given but the response doesn't show it",
                )
            )
    return out


def check_grounding(
    r: dict[str, Any], holdout: set[str] | None, sent_text: str
) -> list[Check]:
    out: list[Check] = []
    precs = r["precedents"]
    ids = [p["ticket_id"] for p in precs]
    if len(precs) > 5:
        out.append(
            Check("precedents", "fail", "RAG", f"{len(precs)} precedents (max 5)")
        )
    elif len(precs) < 3:
        out.append(
            Check("precedents", "warn", "RAG", f"{len(precs)} precedents (spec 3-5)")
        )
    sims = [p["similarity"] for p in precs]
    if sims != sorted(sims, reverse=True):
        out.append(Check("precedents", "fail", "RAG", "not sorted by similarity desc"))
    if len(set(ids)) != len(ids):
        out.append(Check("precedents", "warn", "RAG", "same ticket_id listed twice"))
    if holdout is not None:
        leaked = sorted(set(ids) & holdout)
        if leaked:
            out.append(
                Check("LEAKAGE", "fail", "RAG", f"holdout ids in precedents: {leaked}")
            )
    draft = r.get("draft")
    if draft:
        cited = set(CITED_ID_RE.findall(draft["text"])) | set(draft["citations"])
        stray = sorted(cited - set(ids))
        if stray:
            out.append(
                Check(
                    "citations", "fail", "RAG", f"cited but not in precedents: {stray}"
                )
            )
            if r["guardrails"]["citations_valid"]:
                out.append(
                    Check(
                        "citations",
                        "fail",
                        "guardrails",
                        "citations_valid=true but citations are not all in precedents",
                    )
                )
        if not CITED_ID_RE.search(draft["text"]) and precs:
            out.append(
                Check("citations", "warn", "RAG", "draft cites no [TKT-…] inline")
            )
        if draft["language"] != r["input"]["language_detected"]:
            out.append(
                Check(
                    "draft-language",
                    "fail",
                    "RAG",
                    f"draft.language={draft['language']} but input is "
                    f"{r['input']['language_detected']}",
                )
            )
        guessed = guess_language(draft["text"])
        if guessed and guessed != draft["language"]:
            out.append(
                Check(
                    "draft-language",
                    "fail",
                    "RAG",
                    f"draft text reads as {guessed} but draft.language={draft['language']}",
                )
            )
        if PLACEHOLDER_RE.search(draft["text"]):
            out.append(Check("pii", "warn", "guardrails", "mask placeholder in draft"))
    # Evidence is highlighted in the input pane, so it should be a real substring.
    echoed = r["input"].get("body") or ""
    for k in ("prompt_injection", "unsupported_request"):
        g = r["guardrails"][k]
        if g["flagged"]:
            ev = g.get("evidence")
            if not ev:
                out.append(Check("evidence", "warn", "guardrails", f"{k}: no evidence"))
            elif ev not in sent_text and ev not in echoed:
                out.append(
                    Check(
                        "evidence",
                        "warn",
                        "guardrails",
                        f"{k} evidence not in ticket, UI can't highlight: {ev[:50]!r}",
                    )
                )
    return out


def guess_language(text: str) -> str | None:
    words = re.findall(r"[a-zäöüß]+", text.lower())
    en = sum(w in EN_WORDS for w in words)
    de = sum(w in DE_WORDS for w in words)
    if en + de < 6:
        return None
    if en >= 2 * de + 3:
        return "en"
    if de >= 2 * en + 3:
        return "de"
    return None


def check_latency(r: dict[str, Any], measured_ms: float) -> list[Check]:
    total = r["latency_ms"]["total"]
    if total <= 0:
        return [Check("latency", "warn", "API", f"latency_ms.total={total}")]
    if total > measured_ms + 250:
        return [
            Check(
                "latency",
                "warn",
                "API",
                f"reported {total} > measured {measured_ms:.0f} ms",
            )
        ]
    return []


# --- Per-ticket expectations ----------------------------------------------------


def check_expect(t: dict[str, Any], res: Result, r: Any, strict: bool) -> list[Check]:
    exp = t["expect"]
    out: list[Check] = []
    soft = "fail" if strict else "warn"
    want_http = exp.get("http_status", [200])
    if res.http_status not in want_http:
        got = f"{res.http_status} {res.error_code or ''}".strip()
        out.append(Check("http-status", "fail", "API", f"got {got}, want {want_http}"))
        return out
    if res.http_status != 200:
        codes = exp.get("error_code")
        if codes and res.error_code not in codes:
            out.append(
                Check("error-code", "warn", "API", f"{res.error_code}, want {codes}")
            )
        return out

    status = r["escalation"].get("status")
    codes = sorted(res.reasons)
    if "status" in exp and status not in exp["status"]:
        expected = exp.get("reasons_any", []) + exp.get("reasons_prefer", [])
        owner = REASON_OWNER.get(expected[0], "gate") if expected else "gate"
        out.append(
            Check("expect-status", "fail", owner, f"{status}, want {exp['status']}")
        )
    if exp.get("prefer_status") and status != exp["prefer_status"]:
        out.append(
            Check(
                "prefer-status",
                "warn",
                "gate",
                f"{status}, prefer {exp['prefer_status']}",
            )
        )
    if exp.get("reasons_any") and not any(
        reason_satisfied(c, r) for c in exp["reasons_any"]
    ):
        owner = REASON_OWNER.get(exp["reasons_any"][0], "gate")
        out.append(
            Check(
                "expect-reasons",
                "fail",
                owner,
                f"{codes}, want one of {exp['reasons_any']}",
            )
        )
    if exp.get("reasons_prefer") and not any(
        reason_satisfied(c, r) for c in exp["reasons_prefer"]
    ):
        owner = REASON_OWNER.get(exp["reasons_prefer"][0], "gate")
        out.append(
            Check(
                "prefer-reasons",
                "warn",
                owner,
                f"{codes}, prefer {exp['reasons_prefer']}",
            )
        )
    for head, want in exp.get("labels", {}).items():
        allowed = want if isinstance(want, list) else [want]
        got = res.labels.get(head)
        if got not in allowed:
            out.append(
                Check(f"label-{head}", soft, "classifier", f"{got!r}, want {allowed}")
            )
    detected = r["input"]["language_detected"]
    if exp.get("language") and detected != exp["language"]:
        out.append(
            Check(
                "language", "fail", "guardrails", f"{detected}, want {exp['language']}"
            )
        )
    if "language_supported" in exp:
        got = r["input"].get("language_supported")
        if got is None:
            got = detected in LANGUAGES
        if got != exp["language_supported"]:
            out.append(
                Check(
                    "language",
                    "fail",
                    "guardrails",
                    f"language_supported={got} ({detected}), want {exp['language_supported']}",
                )
            )
    draft = r.get("draft")
    if draft:
        owner = "guardrails" if t["category"] in GUARDED_CATEGORIES else "RAG"
        for pattern in exp.get("draft_must_not_contain", []):
            m = re.search(pattern, draft["text"], re.IGNORECASE)
            if m:
                out.append(
                    Check("draft-content", "fail", owner, f"draft says {m.group(0)!r}")
                )
    if exp.get("pii_values"):
        inp = r["input"]
        found = sum(v for v in (inp.get("pii_counts") or {}).values() if _is_num(v))
        found = max(found, len(inp.get("pii_masked") or []))
        if found < len(exp["pii_values"]):
            out.append(
                Check(
                    "pii",
                    "warn",
                    "guardrails",
                    f"{found} PII items detected, ticket has {len(exp['pii_values'])}",
                )
            )
    return out


# --- Running ----------------------------------------------------------------------


def run_one(
    t: dict[str, Any],
    base_url: str,
    timeout: float,
    holdout: set[str] | None,
    strict: bool,
    barrier: threading.Barrier | None = None,
) -> Result:
    res = Result(id=t["id"], category=t["category"])
    payload = {"subject": t.get("subject"), "body": t["body"]}
    if barrier is not None:
        try:
            barrier.wait(timeout=10)
        except threading.BrokenBarrierError:
            pass
    status, body, err, latency = post_json(f"{base_url}/api/triage", payload, timeout)
    res.http_status, res.latency_ms, res.transport_error = (
        status,
        round(latency, 1),
        err,
    )
    if err:
        res.checks.append(Check("transport", "fail", "API", err))
        return res
    res.response = body
    if status != 200:
        if isinstance(body, dict) and isinstance(body.get("error"), dict):
            res.error_code = body["error"].get("code")
        else:
            res.checks.append(
                Check("error-shape", "fail", "API", f"HTTP {status} without error body")
            )
        res.checks += check_expect(t, res, body, strict)
        return res
    if not isinstance(body, dict):
        res.checks.append(Check("shape", "fail", "API", "200 but body is not JSON"))
        return res
    shape = check_shape(body)
    res.checks += shape
    if any(c.severity == "fail" for c in shape):  # later checks need the shape
        return res
    cls = body["classification"]
    res.labels = {h: cls[h]["label"] for h in ("type", "queue", "priority")}
    res.escalation_status = body["escalation"].get("status")
    res.reasons = [x["code"] for x in body["escalation"]["reasons"]]
    res.precedent_ids = [p["ticket_id"] for p in body["precedents"]]
    sent_text = f"{t.get('subject') or ''}\n{t['body']}"
    res.checks += check_vocabulary(body)
    res.checks += check_gate(body)
    res.checks += check_grounding(body, holdout, sent_text)
    res.checks += check_latency(body, latency)
    res.checks += check_expect(t, res, body, strict)
    return res


def group_checks(
    tickets: list[dict[str, Any]], results: list[Result]
) -> list[dict[str, Any]]:
    """Duplicates must get the same decision; an outage burst should share precedents."""
    by_id = {r.id: r for r in results}
    groups: dict[str, list[tuple[dict[str, Any], Result]]] = defaultdict(list)
    for t in tickets:
        if t.get("group") and t["id"] in by_id:
            groups[t["group"]].append((t, by_id[t["id"]]))
    out = []
    for name, members in sorted(groups.items()):
        ok = [r for _, r in members if r.http_status == 200 and r.escalation_status]
        if len(ok) < 2:
            continue
        ids = [r.id for r in ok]
        found: list[tuple[str, str, str]] = []  # (severity, owner, detail)
        if members[0][0]["category"] == "duplicate":
            statuses = sorted({r.escalation_status or "" for r in ok})
            if len(statuses) > 1:
                found.append(
                    ("fail", "gate", f"same ticket, different status: {statuses}")
                )
            if len({json.dumps(r.labels, sort_keys=True) for r in ok}) > 1:
                found.append(("warn", "classifier", "same ticket, different labels"))
        elif not set.intersection(*(set(r.precedent_ids) for r in ok)):
            found.append(
                ("warn", "RAG", "near-duplicate outage tickets share no precedent")
            )
        out += [
            {"group": name, "severity": s, "owner": o, "members": ids, "detail": d}
            for s, o, d in found
        ]
    return out


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile."""
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, -(-len(ordered) * pct // 100) - 1))
    return ordered[int(k)]


def fmt_ms(v: float) -> str:
    return f"{v:,.0f}"


def usage_totals(results: list[Result]) -> dict[str, float]:
    tokens = cost = 0.0
    for r in results:
        u = r.response.get("usage") if isinstance(r.response, dict) else None
        if isinstance(u, dict):
            tokens += u.get("total_tokens") or 0
            cost += u.get("estimated_cost_usd") or 0
    return {"total_tokens": tokens, "estimated_cost_usd": round(cost, 4)}


def print_summary(
    results: list[Result], groups: list[dict[str, Any]], wall_s: float
) -> None:
    cats: dict[str, list[Result]] = defaultdict(list)
    for r in results:
        cats[r.category].append(r)
    header = f"{'category':<17} {'n':>3} {'pass':>4} {'warn':>4} {'fail':>4} {'p50 ms':>8} {'max ms':>8}"
    print("\n" + header)
    print("-" * len(header))
    for cat, rs in cats.items():
        lat = [r.latency_ms for r in rs if r.latency_ms is not None]
        nfail = sum(1 for r in rs if r.fails())
        nwarn = sum(1 for r in rs if r.warns() and not r.fails())
        print(
            f"{cat:<17} {len(rs):>3} {len(rs) - nfail - nwarn:>4} {nwarn:>4} {nfail:>4} "
            f"{fmt_ms(percentile(lat, 50)):>8} {fmt_ms(max(lat, default=0)):>8}"
        )
    ok_lat = [r.latency_ms for r in results if r.http_status == 200 and r.latency_ms]
    errors = [r for r in results if r.transport_error or (r.http_status or 0) >= 500]
    usage = usage_totals(results)
    print("-" * len(header))
    print(
        f"latency (200s, n={len(ok_lat)}): p50 {fmt_ms(percentile(ok_lat, 50))} ms · "
        f"p95 {fmt_ms(percentile(ok_lat, 95))} ms · max {fmt_ms(max(ok_lat, default=0))} ms"
    )
    print(
        f"errors (transport/5xx): {len(errors)} · requests: {len(results)} · "
        f"wall: {wall_s:.1f} s · usage: {usage['total_tokens']:,.0f} tokens, "
        f"${usage['estimated_cost_usd']}"
    )
    owners = Counter(c.owner for r in results for c in r.fails())
    owners.update(g["owner"] for g in groups if g["severity"] == "fail")
    if owners:
        print(
            "fails by owner: " + ", ".join(f"{o} {n}" for o, n in owners.most_common())
        )
    for title, sev in (("FAILS", "fail"), ("WARNS", "warn")):
        # Identical findings are collapsed into one line with the ticket ids.
        seen: dict[tuple[str, str, str], list[str]] = defaultdict(list)
        for r in results:
            for c in r.checks:
                if c.severity == sev:
                    seen[(c.owner, c.name, c.detail)].append(r.id)
        if seen:
            print(f"\n{title}")
        for (owner, name, detail), ids in seen.items():
            who = ids[0] if len(ids) == 1 else f"{len(ids)}x"
            more = (
                ""
                if len(ids) == 1
                else f"  [{', '.join(ids[:4])}{', …' * (len(ids) > 4)}]"
            )
            print(f"  {who:<10} {owner:<10} {name:<15} {detail}{more}")
    if groups:
        print("\nGROUPS")
        for g in groups:
            print(
                f"  {g['group']:<10} {g['severity']:<10} {g['owner']:<10} {g['detail']}"
            )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SentinelDesk /api/triage stress runner")
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--tickets", type=Path, default=HERE / "tickets.jsonl")
    p.add_argument("--concurrency", type=int, default=1, help="parallel requests")
    p.add_argument("--limit", type=int, help="send only the first N selected tickets")
    p.add_argument("--only", action="append", metavar="CATEGORY", help="repeatable")
    p.add_argument("--id", action="append", dest="ids", metavar="ID", help="repeatable")
    p.add_argument("--holdout-csv", type=Path, help="data/prepared/holdout_inputs.csv")
    p.add_argument("--burst", type=int, metavar="N", help="fire N requests at once")
    p.add_argument(
        "--timeout", type=float, default=30.0, help="per request, s (UI: 30)"
    )
    p.add_argument(
        "--max-requests",
        type=int,
        default=100,
        help="refuse to send more than this many requests (LLM credits)",
    )
    p.add_argument("--strict", action="store_true", help="WARN counts as FAIL")
    p.add_argument("--dry-run", action="store_true", help="list requests, send none")
    p.add_argument(
        "--out", type=Path, help="results file (default stress/results-*.json)"
    )
    return p.parse_args(argv)


def select(
    tickets: list[dict[str, Any]], args: argparse.Namespace
) -> list[dict[str, Any]]:
    chosen = tickets
    if args.only:
        known = {t["category"] for t in tickets}
        unknown = set(args.only) - known
        if unknown:
            usage_error(f"unknown category {sorted(unknown)}; known: {sorted(known)}")
        chosen = [t for t in chosen if t["category"] in args.only]
    if args.ids:
        chosen = [t for t in chosen if t["id"] in args.ids]
    if args.burst:
        # Only tickets that should succeed; cycle them to reach N requests.
        pool = [t for t in chosen if 200 in t["expect"].get("http_status", [200])]
        if not pool:
            usage_error("no tickets to burst with")
        chosen = [
            {
                **pool[i % len(pool)],
                "id": f"{pool[i % len(pool)]['id']}#{i}",
                "group": None,
            }
            for i in range(args.burst)
        ]
    if args.limit:
        chosen = chosen[: args.limit]
    return chosen


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    base_url = args.base_url.rstrip("/")
    tickets = load_tickets(args.tickets)
    chosen = select(tickets, args)
    if not chosen:
        print("no tickets selected", file=sys.stderr)
        return 2
    if len(chosen) > args.max_requests:
        print(
            f"refusing to send {len(chosen)} requests (> --max-requests "
            f"{args.max_requests}). Each one costs LLM calls.",
            file=sys.stderr,
        )
        return 2
    holdout = load_holdout_ids(args.holdout_csv) if args.holdout_csv else None
    concurrency = args.burst or max(1, args.concurrency)

    if args.dry_run:
        for t in chosen:
            print(f"{t['id']:<12} {t['category']:<17} {len(t['body']):>6} chars")
        print(
            f"\n{len(chosen)} requests would go to {base_url} (concurrency {concurrency})"
        )
        return 0

    health = get_health(base_url)
    if health:
        stages = health.get("stages", {})
        modes = ", ".join(
            f"{k}={v.get('mode', '?')}"
            for k, v in stages.items()
            if isinstance(v, dict)
        )
        print(f"health: {health.get('status')} {modes}")
    else:
        print("health: /api/health not reachable (continuing)")
    if holdout is not None:
        print(f"holdout ids loaded: {len(holdout)}")
    print(
        f"sending {len(chosen)} requests to {base_url}/api/triage, concurrency {concurrency}\n"
    )

    barrier = threading.Barrier(len(chosen)) if args.burst else None
    started = datetime.now()
    t0 = time.perf_counter()
    lock = threading.Lock()

    def task(t: dict[str, Any]) -> Result:
        res = run_one(t, base_url, args.timeout, holdout, args.strict, barrier)
        if args.burst:  # the functional pass judges content; a burst judges load
            for c in res.checks:
                if c.severity == "fail" and c.name not in LOAD_FAILS:
                    c.severity = "warn"
        mark = "FAIL" if res.fails() else ("warn" if res.warns() else "ok")
        first = (res.fails() or res.warns() or [None])[0]
        note = f"{first.name}: {first.detail}" if first else ""
        status = res.escalation_status or res.error_code or res.transport_error or ""
        with lock:
            print(
                f"  {mark:<4} {res.id:<12} {res.category:<17} "
                f"{fmt_ms(res.latency_ms or 0):>7} ms  {status[:12]:<12} {note[:70]}"
            )
        return res

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(task, chosen))
    wall = time.perf_counter() - t0
    groups = group_checks(chosen, results)
    if args.strict:
        for g in groups:
            g["severity"] = "fail"
    print_summary(results, groups, wall)

    ok_lat = [r.latency_ms for r in results if r.http_status == 200 and r.latency_ms]
    failed_tickets = sum(1 for r in results if r.fails())
    failed_groups = sum(1 for g in groups if g["severity"] == "fail")
    warned = sum(1 for r in results if r.warns())
    report = {
        "started_at": started.isoformat(timespec="seconds"),
        "base_url": base_url,
        "args": {
            k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()
        },
        "health": health,
        "summary": {
            "requests": len(results),
            "failed_tickets": failed_tickets,
            "failed_groups": failed_groups,
            "warned_tickets": warned,
            "errors": sum(
                1 for r in results if r.transport_error or (r.http_status or 0) >= 500
            ),
            "latency_ms": {
                "p50": percentile(ok_lat, 50),
                "p95": percentile(ok_lat, 95),
                "max": max(ok_lat, default=0),
            },
            "usage": usage_totals(results),
            "wall_s": round(wall, 2),
        },
        "groups": groups,
        "results": [asdict(r) for r in results],
    }
    out = args.out or HERE / f"results-{started:%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nresults: {out}")
    failed = failed_tickets + failed_groups > 0 or (args.strict and warned > 0)
    print("RESULT: FAIL" if failed else "RESULT: PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
