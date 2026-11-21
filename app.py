"""Explainable Streamlit console for the five-stage SentinelDesk workflow.

Run with:

    streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from sentineldesk.app_factory import create_orchestrator
from sentineldesk.audit import build_audit_event
from sentineldesk.classifier_interface import MockClassifier
from sentineldesk.guardrails import mask_pii
from sentineldesk.schemas import (
    AUTO_DRAFT_READY,
    ESCALATE_IMMEDIATELY,
    TriageResult,
)

st.set_page_config(page_title="SentinelDesk", page_icon="🛡️", layout="wide")


@st.cache_resource(show_spinner="Loading classifier and precedent index…")
def load_orchestrator(judge_mode: bool):
    """Load expensive models once; judge mode refuses every mock fallback."""
    return create_orchestrator(allow_mock=not judge_mode)


def label_rows(result: TriageResult) -> list[dict[str, object]]:
    """Keep calibrated model confidence distinct from RAG vote share."""
    rows = []
    for head in ("type", "queue", "priority"):
        classifier = result.classifier_labels.head(head)
        rag = result.rag_labels.head(head) if result.rag_labels else None
        rows.append(
            {
                "head": head.title(),
                "classifier label": classifier.label or "Not run",
                "classifier confidence": (
                    classifier.confidence if classifier.probabilities else None
                ),
                "classifier margin": (
                    classifier.margin if classifier.probabilities else None
                ),
                "RAG vote": rag.label if rag else "—",
                "RAG vote share": rag.confidence if rag else None,
                "final label": result.final_labels.head(head).label or "Not run",
            }
        )
    return rows


def render_status(result: TriageResult) -> None:
    """Show the policy outcome before the supporting detail."""
    message = result.reasons[0] if result.reasons else "All automated checks passed."
    if result.status == AUTO_DRAFT_READY:
        st.success(f"Verified draft ready — {message}")
    elif result.status == ESCALATE_IMMEDIATELY:
        st.error(f"Immediate escalation — {message}")
    else:
        st.warning(f"Human review required — {message}")


def render_result(result: TriageResult) -> None:
    """Render the evidence and measurements judges need to inspect."""
    render_status(result)

    st.subheader("1. Independent classification and RAG evidence")
    metrics = st.columns(3)
    for column, head in zip(metrics, ("type", "queue", "priority")):
        distribution = result.classifier_labels.head(head)
        if not distribution.probabilities:
            column.metric(head.title(), "Not run")
            continue
        column.metric(
            head.title(),
            distribution.label,
            f"{distribution.confidence:.0%} confidence",
        )
        column.caption(f"Top-two margin: {distribution.margin:.0%}")

    labels = pd.DataFrame(label_rows(result)).set_index("head")
    st.dataframe(
        labels,
        width="stretch",
        column_config={
            "classifier confidence": st.column_config.ProgressColumn(
                min_value=0.0, max_value=1.0, format="percent"
            ),
            "classifier margin": st.column_config.ProgressColumn(
                min_value=0.0, max_value=1.0, format="percent"
            ),
            "RAG vote share": st.column_config.ProgressColumn(
                min_value=0.0, max_value=1.0, format="percent"
            ),
        },
    )
    if result.classifier_labels.source == "not_run":
        st.caption("Classifier and RAG inference were skipped by the input guardrails.")
    else:
        score_kind = (
            "a development heuristic score"
            if result.runtime_backends.get("classifier") == "MockClassifier"
            else "calibrated model output"
        )
        st.caption(
            f"Classifier confidence is {score_kind}. RAG vote share is a separate "
            "historical-agreement signal and is never averaged into it."
        )

    st.subheader("2. Decision engine")
    decision_columns = st.columns(4)
    decision_columns[0].metric("Route", result.route.upper())
    decision_columns[1].metric(
        "Evidence", "SUFFICIENT" if result.evidence_sufficient else "WEAK"
    )
    decision_columns[2].metric("Best match", f"{result.top_similarity:.1%}")
    decision_columns[3].metric("Total latency", f"{result.latency_ms:.0f} ms")
    if result.route_reasons:
        st.write(
            "Routing signals:", *[f"- {reason}" for reason in result.route_reasons]
        )
    if result.reasons:
        st.write("Policy reasons:", *[f"- {reason}" for reason in result.reasons])

    st.subheader("3. Retrieved historical evidence")
    if not result.precedents:
        st.info("No historical tickets were retrieved.")
    for precedent in result.precedents:
        with st.expander(
            f"{precedent.ticket_id} · similarity {precedent.similarity:.1%} · "
            f"{precedent.type} / {precedent.priority}"
        ):
            safe_snippet, _ = mask_pii(precedent.answer_snippet(800))
            st.write(safe_snippet)

    st.subheader("4. Grounded draft and independent verifier")
    if result.draft_reply:
        draft_label = (
            "Verified draft"
            if result.status == AUTO_DRAFT_READY
            else "Rejected candidate draft — do not send"
        )
        st.text_area(draft_label, result.draft_reply, height=240)
    else:
        st.info("Drafting was skipped because a safety or evidence gate stopped it.")
    if result.grounding_review:
        st.json(result.grounding_review, expanded=True)
    if result.verification_issues:
        st.error("Verification issues: " + "; ".join(result.verification_issues))

    st.subheader("5. Measured execution")
    timing = pd.DataFrame(
        [
            {"stage": stage.replace("_", " ").title(), "milliseconds": duration}
            for stage, duration in result.stage_latency_ms.items()
        ]
    )
    if not timing.empty:
        st.bar_chart(timing.set_index("stage"))
    st.caption(
        f"{result.total_tokens:,} tokens · estimated cost "
        f"${result.estimated_cost_usd:.6f} · "
        f"{len(result.llm_calls)} LLM call(s)"
    )
    with st.expander("Redacted security audit event"):
        st.json(build_audit_event(result), expanded=False)
    with st.expander("Detailed result JSON (trusted UI only)"):
        st.json(result.to_dict(), expanded=False)


st.title("🛡️ SentinelDesk")
st.caption(
    "Secure multilingual ticket triage with calibrated classification, independent "
    "historical evidence, deterministic escalation, and adversarial verification."
)

judge_mode = st.sidebar.toggle(
    "Judge mode (require real artifacts)",
    value=False,
    help=(
        "Stops startup unless trained models, the prepared multilingual FAISS "
        "index, and Gemini credentials are all available."
    ),
)

try:
    orchestrator = load_orchestrator(judge_mode)
except (RuntimeError, ValueError) as error:
    st.error(str(error))
    st.stop()

is_mock = isinstance(orchestrator.classifier, MockClassifier)
knowledge_base_size = len(orchestrator.precedent_index.tickets)
if is_mock or knowledge_base_size <= 16 or orchestrator.llm_provider.name == "mock":
    st.warning(
        "DEVELOPMENT MODE: one or more backends are mocked. Enable Judge mode after "
        "training the classifier, building the index, and configuring Gemini."
    )
else:
    st.success("REAL ARTIFACTS: trained classifier and saved precedent index loaded.")

with st.form("ticket"):
    subject = st.text_input("Subject", "Hospital VPN unavailable")
    body = st.text_area(
        "Customer message",
        "Our hospital VPN is down. Doctors cannot access patient records.",
        height=150,
    )
    submitted = st.form_submit_button("Triage ticket", type="primary")

if submitted:
    with st.spinner("Running all five stages…"):
        render_result(orchestrator.triage(subject, body))
