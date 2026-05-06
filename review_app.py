"""
Streamlit app for blind defect-labeling of synthetic eviction notices.

Usage:
    streamlit run review_app.py

Reviewers see each notice's text and tick which of the 9 MVP defects they
believe are present. Feedback is saved per reviewer to
`synthetic_notices/output/LLM_generated/feedback/<batch-stem>__<user>__feedback.json`
for downstream use (training data, generator-quality audits, etc.).
"""

import base64
import copy
import json
import os
import re
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st

from synthetic_notices import reviewer_assignment


BATCH_DIR = Path(os.environ.get("BATCH_DIR", "synthetic_notices/output/LLM_generated"))
FEEDBACK_DIR = Path(os.environ.get("FEEDBACK_DIR", str(BATCH_DIR / "feedback")))

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


def list_batch_files():
    if not BATCH_DIR.exists():
        return []
    valid = []
    for p in sorted(BATCH_DIR.glob("*.json")):
        if not p.is_file():
            continue
        if p.name.endswith(reviewer_assignment.MANIFEST_SUFFIX):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        valid.append(p)
    return valid


def load_batch(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("notices", [])


def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def _allowed_emails() -> set[str]:
    """Lowercased set of emails permitted to use the app. Empty if no secrets configured."""
    try:
        raw = st.secrets.get("allowed_emails", [])
    except Exception:
        return set()
    return {e.strip().lower() for e in raw if e}


def feedback_path_for(batch_path, user_slug):
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    return FEEDBACK_DIR / f"{batch_path.stem}__{user_slug}__feedback.json"


def load_feedback(batch_path, user_slug):
    path = feedback_path_for(batch_path, user_slug)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"batch_file": batch_path.name, "reviewer": user_slug, "reviews": {}}


def _github_persistence_configured() -> bool:
    """True if st.secrets has the keys needed to commit feedback to GitHub."""
    try:
        if "github" not in st.secrets:
            return False
    except Exception:
        return False
    cfg = st.secrets["github"]
    return all(k in cfg for k in ("token", "owner", "repo", "branch"))


def _commit_feedback_to_github(filename: str, content: str, reviewer: str) -> None:
    """Create or update a single feedback file in the configured GitHub repo
    via the Contents API. Raises on failure; caller decides how to surface."""
    cfg = st.secrets["github"]
    token, owner, repo, branch = cfg["token"], cfg["owner"], cfg["repo"], cfg["branch"]
    feedback_subdir = cfg.get("feedback_dir", "feedback")
    remote_path = f"{feedback_subdir}/{filename}"
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{remote_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = {
        "message": f"Update feedback for {reviewer}",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }

    def _fetch_sha() -> str | None:
        r = requests.get(api_url, headers=headers, params={"ref": branch}, timeout=15)
        if r.status_code == 200:
            return r.json().get("sha")
        if r.status_code == 404:
            return None
        r.raise_for_status()

    # Streamlit auto-saves on every checkbox tick; back-to-back saves can race
    # against GitHub's replication, so a stale sha returns 409. Retry once with
    # the latest sha before surfacing the failure.
    for attempt in range(2):
        sha = _fetch_sha()
        if sha:
            body["sha"] = sha
        else:
            body.pop("sha", None)
        r = requests.put(api_url, headers=headers, json=body, timeout=15)
        if r.status_code != 409 or attempt == 1:
            r.raise_for_status()
            return


def save_feedback(batch_path, user_slug, data):
    path = feedback_path_for(batch_path, user_slug)
    content = json.dumps(data, indent=2)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    # Durable persistence on Streamlit Cloud (where the local file is ephemeral).
    if _github_persistence_configured():
        try:
            _commit_feedback_to_github(path.name, content, user_slug)
        except Exception as exc:
            st.warning(f"Saved locally but GitHub sync failed: {exc}")


def count_reviewers_for(batch_path, notice_index):
    """How many distinct reviewers have left feedback for this notice?"""
    pattern = f"{batch_path.stem}__*__feedback.json"
    key = str(notice_index)
    count = 0
    for p in FEEDBACK_DIR.glob(pattern):
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            if key in data.get("reviews", {}):
                count += 1
        except Exception:
            continue
    return count


# ============================ App ============================

st.set_page_config(page_title="Notice Review", layout="wide")
st.title("Synthetic Notice Review")

st.markdown(
    """
    <style>
    .stTextArea textarea[disabled] {
        color: #1a1a1a !important;
        -webkit-text-fill-color: #1a1a1a !important;
        opacity: 1 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---- Google sign-in (gates the rest of the UI) ----
# `st.user.is_logged_in` only exists when [auth] is configured in secrets.toml.
# Without OIDC config, fail fast with a useful message instead of an AttributeError.
try:
    is_logged_in = st.user.is_logged_in
except AttributeError:
    st.error(
        "OIDC sign-in is not configured. Add an `[auth]` block to `.streamlit/secrets.toml` "
        "with `client_id`, `client_secret`, `cookie_secret`, `redirect_uri`, and "
        "`server_metadata_url`. See `.streamlit/secrets.toml.example` for the template."
    )
    st.stop()

if not is_logged_in:
    st.info("Sign in with your Google account to start reviewing.")
    if st.button("Sign in with Google", type="primary"):
        st.login("google")
    st.stop()

email = (st.user.email or "").lower()
allowed = _allowed_emails()
if not allowed:
    st.error("Allowlist is empty. Configure `allowed_emails` in `.streamlit/secrets.toml`.")
    st.stop()
if email not in allowed:
    st.error(f"Access denied for `{email}`. Contact the project owner to be added.")
    if st.button("Sign out"):
        st.logout()
    st.stop()

username = email
display_name = st.user.name or email
user_slug = _slugify(username)

with st.sidebar:
    st.header("Reviewer")
    st.markdown(f"**{display_name}**  \n`{username}`")
    if st.button("Sign out", key="sidebar_logout"):
        st.logout()

batches = list_batch_files()
if not batches:
    st.warning(f"No valid batches found in `{BATCH_DIR}/`.")
    st.stop()

# ---- Sidebar: batch + navigation ----
with st.sidebar:
    st.header("Configuration")
    batch_path = st.selectbox(
        "Notice batch",
        batches,
        format_func=lambda p: p.name,
    )

try:
    notices = load_batch(batch_path)
except Exception as exc:
    st.error(f"Failed to load `{batch_path.name}`: {exc}")
    st.stop()

if not notices:
    st.warning("No notices in this batch.")
    st.stop()

# Apply per-reviewer assignment if a manifest exists alongside the batch.
# `assigned` is a list of (batch_idx_0based, notice_dict). When no manifest
# exists, every reviewer sees every notice (legacy behavior preserved).
manifest = reviewer_assignment.load_manifest(batch_path)
if manifest is None:
    assigned = list(enumerate(notices))
else:
    indices = reviewer_assignment.assigned_indices_for(manifest, email)
    if not indices:
        st.warning(
            f"You ({email}) have no notices assigned in this batch's manifest. "
            "Contact the project owner if this is unexpected."
        )
        st.stop()
    assigned = [(i, notices[i]) for i in indices if 0 <= i < len(notices)]

total = len(assigned)
shared_set = set(manifest.get("shared_indices", [])) if manifest else set()

idx_state_key = f"idx::{batch_path.name}"
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

    feedback_preview = load_feedback(batch_path, user_slug)
    reviewed_count = len(feedback_preview.get("reviews", {}))
    st.markdown(f"**Your reviews:** {reviewed_count} / {total}")

current_idx = st.session_state[idx_state_key]
batch_idx, current = assigned[current_idx]
# Feedback keys use the original 1-indexed batch position so cross-reviewer
# analysis joins on the same notice regardless of who saw it.
notice_index = batch_idx + 1
display_index = current_idx + 1

# ---- Load existing feedback for this notice ----
feedback = load_feedback(batch_path, user_slug)
review_key = str(notice_index)
review = feedback["reviews"].get(review_key, {})
review.setdefault("notice_index", notice_index)
review.setdefault("comment", "")
review.setdefault("defects_observed", {})
original_review = copy.deepcopy(review)

# ---- Header ----
header_l, header_r = st.columns([3, 1])
with header_l:
    st.subheader(f"Notice {display_index} of {total}")
    if manifest is not None:
        tag = "shared" if batch_idx in shared_set else "unique"
        st.caption(f"Batch index #{notice_index} · {tag}")
with header_r:
    if review.get("reviewed_at"):
        st.caption(f"You last reviewed: {review['reviewed_at']}")
    else:
        st.caption("You haven't reviewed this yet")
    n_reviewers = count_reviewers_for(batch_path, notice_index)
    if n_reviewers > 0:
        st.caption(f"👥 Reviewed by {n_reviewers} reviewer(s) so far")

# ---- Notice text (left) + defect checkboxes (right) ----
# Widget keys are scoped by the original batch index so per-notice state
# stays bound to the notice content (not the reviewer's local position).
def widget_key(kind, defect):
    return f"{kind}::{batch_path.stem}::{batch_idx}::{defect}"

text_col, defects_col = st.columns([3, 2])

with text_col:
    st.subheader("📄 Notice text")
    text = current.get("text", "")
    if text:
        st.text_area(
            "Notice text",
            value=text,
            height=600,
            disabled=True,
            label_visibility="collapsed",
            key=f"notice_text::{batch_path.stem}::{batch_idx}",
        )
    else:
        st.warning("Notice has no text.")

with defects_col:
    st.subheader("Defects you observe in this notice")
    st.caption("Check every defect you believe is present.")
    for d, desc in DEFECT_DESCRIPTIONS.items():
        review["defects_observed"][d] = st.checkbox(
            f"**{d}** — {desc}",
            value=review["defects_observed"].get(d, False),
            key=widget_key("obs", d),
        )

# ---- Comment ----
st.subheader("📝 Comments")
review["comment"] = st.text_area(
    "Comments",
    value=review["comment"],
    key=f"comment::{batch_path.stem}::{batch_idx}",
    height=120,
    label_visibility="collapsed",
    placeholder="Notes about this notice...",
)

# ---- Auto-save (only if anything changed) ----
if review != original_review:
    review["reviewed_at"] = datetime.now().isoformat(timespec="seconds")
    review["reviewer"] = username
    review["reviewer_name"] = display_name
    feedback["reviews"][review_key] = review
    save_feedback(batch_path, user_slug, feedback)
    st.success(f"💾 Saved to `{feedback_path_for(batch_path, user_slug).name}`")
