"""Materialize .streamlit/secrets.toml from Azure App Settings env vars.

Run as the first step of startup.sh on Azure App Service. Secrets live in
the App Service "Configuration → Application settings" panel, not in git.

Required env vars:
  AUTH_CLIENT_ID, AUTH_CLIENT_SECRET, AUTH_COOKIE_SECRET,
  AUTH_REDIRECT_URI, ALLOWED_EMAILS  (comma-separated)

Optional:
  AUTH_SERVER_METADATA_URL  (defaults to Google's discovery URL)
  GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH, GITHUB_FEEDBACK_DIR
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REQUIRED = [
    "AUTH_CLIENT_ID",
    "AUTH_CLIENT_SECRET",
    "AUTH_COOKIE_SECRET",
    "AUTH_REDIRECT_URI",
    "ALLOWED_EMAILS",
]


def _q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> int:
    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if missing:
        print(
            f"[write_secrets] missing required env vars: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    metadata_url = os.environ.get(
        "AUTH_SERVER_METADATA_URL",
        "https://accounts.google.com/.well-known/openid-configuration",
    )
    allowed = [e.strip() for e in os.environ["ALLOWED_EMAILS"].split(",") if e.strip()]
    if not allowed:
        print("[write_secrets] ALLOWED_EMAILS is empty after parsing", file=sys.stderr)
        return 1

    # `allowed_emails` must be top-level (review_app.py reads
    # st.secrets["allowed_emails"]); declare it before any [section] header.
    # Streamlit's `st.login("google")` looks up credentials under
    # [auth.google]; redirect_uri and cookie_secret stay in the parent [auth].
    lines = [
        "# Generated at startup by azure/write_secrets.py — do not commit.",
        "allowed_emails = [" + ", ".join(_q(e) for e in allowed) + "]",
        "",
        "[auth]",
        f"redirect_uri = {_q(os.environ['AUTH_REDIRECT_URI'])}",
        f"cookie_secret = {_q(os.environ['AUTH_COOKIE_SECRET'])}",
        "",
        "[auth.google]",
        f"client_id = {_q(os.environ['AUTH_CLIENT_ID'])}",
        f"client_secret = {_q(os.environ['AUTH_CLIENT_SECRET'])}",
        f"server_metadata_url = {_q(metadata_url)}",
    ]

    gh_keys = ("GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO", "GITHUB_BRANCH")
    if all(os.environ.get(k) for k in gh_keys):
        lines += [
            "",
            "[github]",
            f"token = {_q(os.environ['GITHUB_TOKEN'])}",
            f"owner = {_q(os.environ['GITHUB_OWNER'])}",
            f"repo = {_q(os.environ['GITHUB_REPO'])}",
            f"branch = {_q(os.environ['GITHUB_BRANCH'])}",
            f"feedback_dir = {_q(os.environ.get('GITHUB_FEEDBACK_DIR', 'feedback'))}",
        ]

    out = Path(".streamlit/secrets.toml")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(out, 0o600)
    except OSError:
        pass
    print(f"[write_secrets] wrote {out} (auth + {len(allowed)} allowed_emails)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
