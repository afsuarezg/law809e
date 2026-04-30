"""
Streamlit app for reviewing evaluation reports of synthetic eviction notices.

Usage:
    streamlit run review_app.py

The app reads JSON eval reports from `evaluation/` and lets the user:
- View the notice text (from extracted.raw_text when --debug was used, else from the source batch file)
- See expected vs detected defects
- Tick checkboxes to confirm whether each defect is actually present (ground truth review)
  and whether the automated logic correctly flagged it (logic outcome review)
- Add free-form comments

Feedback auto-saves to `evaluation/feedback/<eval-stem>_feedback.json`.
"""

import copy
import json
from datetime import datetime
from pathlib import Path

import streamlit as st


EVAL_DIR = Path("evaluation")
FEEDBACK_DIR = EVAL_DIR / "feedback"
BATCH_DIR = Path("synthetic_notices/output/LLM_generated")

DEFECT_DESCRIPTIONS = {
    "MVP-001": "Missing disjunctive phrasing ('pay OR quit')",
    "MVP-002": "Insufficient notice period (< 3 business days)",
    "MVP-003": "No exact dollar amount stated",
    "MVP-004": "Missing payee name/phone/address",
    "MVP-005": "Missing payment hours",
    "MVP-006": "Missing financial institution info",
    "MVP-007": "Electronic payment not previously established",
    "MVP-008": "Rent demanded > 1 year old",
    "MVP-009": "No forfeiture declaration",
}


def list_eval_reports():
    if not EVAL_DIR.exists():
        return []
    return sorted(p for p in EVAL_DIR.glob("*.json") if p.is_file())


def load_eval_report(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_runs(report):
    """Return [(label, run_dict), ...] for both single- and multi-model reports."""
    if "runs" in report and "comparison" in report:
        return [
            (run["config"].get("model") or run["config"].get("provider") or f"run_{i+1}", run)
            for i, run in enumerate(report["runs"])
        ]
    label = report.get("config", {}).get("model") or report.get("config", {}).get("provider") or "default"
    return [(label, report)]


def load_batch_text_lookup(batch_filename):
    """Map 1-based notice index → original notice text from the source batch file."""
    if not batch_filename:
        return {}
    batch_path = BATCH_DIR / batch_filename
    if not batch_path.exists():
        return {}
    with open(batch_path, encoding="utf-8") as f:
        batch = json.load(f)
    notices = batch if isinstance(batch, list) else batch.get("notices", [])
    return {i + 1: n.get("text", "") for i, n in enumerate(notices)}


def get_notice_text(notice_result, batch_lookup):
    extracted = notice_result.get("extracted")
    if isinstance(extracted, dict):
        text = extracted.get("raw_text")
        if text:
            return text
    return batch_lookup.get(notice_result["index"], "")


def feedback_path_for(report_path):
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    return FEEDBACK_DIR / f"{report_path.stem}_feedback.json"


def load_feedback(report_path):
    path = feedback_path_for(report_path)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"eval_report": report_path.name, "reviews": {}}


def save_feedback(report_path, data):
    path = feedback_path_for(report_path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ============================ App ============================

st.set_page_config(page_title="Notice Review", layout="wide")
st.title("Synthetic Notice Review")

reports = list_eval_reports()
if not reports:
    st.warning(f"No eval reports found in `{EVAL_DIR}/`. Run `evaluate_notices.py` first.")
    st.stop()

# ---- Sidebar: report + model + navigation ----
with st.sidebar:
    st.header("Configuration")
    report_choice = st.selectbox(
        "Eval report",
        reports,
        format_func=lambda p: p.name,
    )

report = load_eval_report(report_choice)
runs = get_runs(report)

with st.sidebar:
    if len(runs) > 1:
        labels = [label for label, _ in runs]
        model_label = st.selectbox("Model", labels)
        active_run = next(run for label, run in runs if label == model_label)
    else:
        model_label, active_run = runs[0]
        st.markdown(f"**Model:** `{model_label}`")

notices = active_run.get("notices", [])
total = len(notices)
if total == 0:
    st.warning("No notices in this report.")
    st.stop()

idx_state_key = f"idx::{report_choice.name}::{model_label}"
if idx_state_key not in st.session_state:
    st.session_state[idx_state_key] = 0

with st.sidebar:
    st.header("Navigation")
    col1, col2 = st.columns(2)
    if col1.button("◀ Prev", use_container_width=True, disabled=st.session_state[idx_state_key] <= 0):
        st.session_state[idx_state_key] -= 1
        st.rerun()
    if col2.button("Next ▶", use_container_width=True, disabled=st.session_state[idx_state_key] >= total - 1):
        st.session_state[idx_state_key] += 1
        st.rerun()
    new_idx = st.number_input(
        "Notice (1-indexed)",
        min_value=1,
        max_value=total,
        value=st.session_state[idx_state_key] + 1,
        step=1,
    )
    if new_idx - 1 != st.session_state[idx_state_key]:
        st.session_state[idx_state_key] = new_idx - 1
        st.rerun()

    # Show how many notices have been reviewed for this report+model
    feedback_preview = load_feedback(report_choice)
    reviewed_for_model = sum(
        1 for k in feedback_preview.get("reviews", {})
        if k.endswith(f"::{model_label}")
    )
    st.markdown(f"**Reviewed:** {reviewed_for_model} / {total}")

current_idx = st.session_state[idx_state_key]
current = notices[current_idx]

# ---- Resolve batch source for fallback text lookup ----
batch_filename = (
    active_run.get("config", {}).get("file")
    or report.get("config", {}).get("file")
    or report.get("file", "")
)
batch_lookup = load_batch_text_lookup(batch_filename)

# ---- Load existing feedback for this notice ----
feedback = load_feedback(report_choice)
review_key = f"{current['index']}::{model_label}"
review = feedback["reviews"].get(review_key, {})
review.setdefault("notice_index", current["index"])
review.setdefault("model", model_label)
review.setdefault("comment", "")
review.setdefault("expected_present", {})
review.setdefault("detected_correct", {})
original_review = copy.deepcopy(review)

# ---- Header ----
status = "✅ Exact match" if current.get("exact_match") else "❌ Mismatch"
header_l, header_r = st.columns([3, 1])
with header_l:
    st.subheader(f"Notice {current['index']} of {total}")
    st.markdown(f"**Status:** {status}")
with header_r:
    if review.get("reviewed_at"):
        st.caption(f"Last reviewed: {review['reviewed_at']}")
    else:
        st.caption("Not yet reviewed")

if current.get("error"):
    st.error(f"Evaluation error: {current['error']}")

# ---- Notice text ----
text = get_notice_text(current, batch_lookup)
with st.expander("📄 Notice text", expanded=True):
    if text:
        st.text(text)
    else:
        st.warning(
            "Notice text not available. Re-run evaluation with `--debug` to embed text in the report, "
            f"or place the source batch file at `{BATCH_DIR}/{batch_filename or '<batch>.json'}`."
        )

# ---- Defect review (two columns) ----
def widget_key(kind, defect):
    return f"{kind}::{report_choice.stem}::{model_label}::{current_idx}::{defect}"

col_exp, col_det = st.columns(2)

with col_exp:
    st.subheader("Expected (ground truth)")
    st.caption("Check if this defect IS actually present in the notice.")
    expected = current.get("expected", [])
    if not expected:
        st.info("No defects expected (notice should be valid).")
    for d in expected:
        desc = DEFECT_DESCRIPTIONS.get(d, d)
        review["expected_present"][d] = st.checkbox(
            f"**{d}** — {desc}",
            value=review["expected_present"].get(d, True),
            key=widget_key("exp", d),
        )

with col_det:
    st.subheader("Detected (by logic)")
    st.caption("Check if the logic CORRECTLY flagged this defect.")
    detected = current.get("detected", [])
    if not detected:
        st.info("No defects detected by the logic.")
    for d in detected:
        desc = DEFECT_DESCRIPTIONS.get(d, d)
        review["detected_correct"][d] = st.checkbox(
            f"**{d}** — {desc}",
            value=review["detected_correct"].get(d, True),
            key=widget_key("det", d),
        )

# ---- TP/FP/FN summary ----
with st.expander("Confusion matrix details"):
    st.markdown(
        f"- **TP** (in both): `{current.get('tp', [])}`\n"
        f"- **FP** (detected, not expected): `{current.get('fp', [])}`\n"
        f"- **FN** (expected, not detected): `{current.get('fn', [])}`"
    )

# ---- Comment ----
st.subheader("📝 Comments")
review["comment"] = st.text_area(
    "Comments",
    value=review["comment"],
    key=f"comment::{report_choice.stem}::{model_label}::{current_idx}",
    height=120,
    label_visibility="collapsed",
    placeholder="Notes about this notice or evaluation outcome...",
)

# ---- Auto-save (only if anything changed) ----
if review != original_review:
    review["reviewed_at"] = datetime.now().isoformat(timespec="seconds")
    feedback["reviews"][review_key] = review
    save_feedback(report_choice, feedback)
    st.success(f"💾 Saved to `{feedback_path_for(report_choice).name}`")
