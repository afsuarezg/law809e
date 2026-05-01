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
import streamlit_authenticator as stauth
import yaml


BATCH_DIR = Path(os.environ.get("BATCH_DIR", "synthetic_notices/output/LLM_generated"))
FEEDBACK_DIR = Path(os.environ.get("FEEDBACK_DIR", str(BATCH_DIR / "feedback")))
AUTH_CONFIG_PATH = Path(os.environ.get("AUTH_CONFIG_PATH", "auth_config.yaml"))

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
    return sorted(p for p in BATCH_DIR.glob("*.json") if p.is_file())


def load_batch(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("notices", [])


def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def _load_auth_config() -> dict:
    """Return the auth config dict.

    Streamlit Cloud: from st.secrets['auth'] (TOML-based).
    Local dev: from auth_config.yaml. The yaml.safe_load returns mutable dicts;
    st.secrets entries are roundtripped via JSON to give plain mutable dicts
    (streamlit-authenticator mutates them at runtime to track login state)."""
    try:
        has_auth_secret = "auth" in st.secrets
    except Exception:
        # No secrets.toml configured (typical for local dev) — fall through to YAML.
        has_auth_secret = False
    if has_auth_secret:
        return json.loads(json.dumps(dict(st.secrets["auth"])))
    if AUTH_CONFIG_PATH.exists():
        with open(AUTH_CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f)
    st.error(
        f"No auth config found. Configure `st.secrets['auth']` (Streamlit Cloud) "
        f"or create `{AUTH_CONFIG_PATH}` locally:\n\n"
        "```\npython manage_auth_users.py init\n"
        "python manage_auth_users.py add --username <user> --name \"<Name>\" --email <email>\n```"
    )
    st.stop()


def load_authenticator():
    """Build the Authenticator. Not cached: it instantiates a CookieManager
    widget internally, which Streamlit forbids inside cached functions."""
    config = _load_auth_config()
    return stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )


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
    sha = None
    r = requests.get(api_url, headers=headers, params={"ref": branch}, timeout=15)
    if r.status_code == 200:
        sha = r.json().get("sha")
    elif r.status_code != 404:
        r.raise_for_status()
    body = {
        "message": f"Update feedback for {reviewer}",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha
    r = requests.put(api_url, headers=headers, json=body, timeout=15)
    r.raise_for_status()


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

# ---- Login (gates the rest of the UI) ----
authenticator = load_authenticator()

try:
    authenticator.login(location="main")
except Exception as exc:
    st.error(f"Login error: {exc}")
    st.stop()

auth_status = st.session_state.get("authentication_status")
if auth_status is False:
    st.error("Username or password is incorrect.")
    st.stop()
if auth_status is None:
    st.info("Please log in to start reviewing.")
    st.stop()

# Authenticated from here on.
username = st.session_state["username"]
display_name = st.session_state.get("name") or username
user_slug = _slugify(username)

with st.sidebar:
    st.header("Reviewer")
    st.markdown(f"**{display_name}**  \n`{username}`")
    authenticator.logout(location="sidebar")

batches = list_batch_files()
if not batches:
    st.warning(f"No batches found in `{BATCH_DIR}/`.")
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

total = len(notices)
if total == 0:
    st.warning("No notices in this batch.")
    st.stop()

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
current = notices[current_idx]
notice_index = current_idx + 1

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
    st.subheader(f"Notice {notice_index} of {total}")
with header_r:
    if review.get("reviewed_at"):
        st.caption(f"You last reviewed: {review['reviewed_at']}")
    else:
        st.caption("You haven't reviewed this yet")
    n_reviewers = count_reviewers_for(batch_path, notice_index)
    if n_reviewers > 0:
        st.caption(f"👥 Reviewed by {n_reviewers} reviewer(s) so far")

# ---- Notice text (left) + defect checkboxes (right) ----
def widget_key(kind, defect):
    return f"{kind}::{batch_path.stem}::{current_idx}::{defect}"

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
            key=f"notice_text::{batch_path.stem}::{current_idx}",
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
    key=f"comment::{batch_path.stem}::{current_idx}",
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
