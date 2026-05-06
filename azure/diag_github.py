"""Replicate review_app._commit_feedback_to_github exactly, against a
sentinel filename, so we can see what HTTP status GitHub returns when
the running container makes the call. Run via:

    python3 azure/diag_github.py

Reads .streamlit/secrets.toml the same way Streamlit does.
"""

from __future__ import annotations

import base64
import sys
import tomllib
from pathlib import Path

import requests


def main() -> int:
    p = Path(".streamlit/secrets.toml")
    if not p.exists():
        print(f"[diag] {p} missing — write_secrets.py didn't run?", file=sys.stderr)
        return 1
    cfg = tomllib.load(p.open("rb")).get("github")
    if not cfg:
        print("[diag] [github] section missing from secrets.toml", file=sys.stderr)
        return 1

    token = cfg.get("token", "")
    owner = cfg.get("owner")
    repo = cfg.get("repo")
    branch = cfg.get("branch")
    fdir = cfg.get("feedback_dir", "feedback")

    print(f"[diag] owner={owner!r} repo={repo!r} branch={branch!r} fdir={fdir!r}")
    print(f"[diag] token len={len(token)} tail={token[-8:]!r}")

    api = f"https://api.github.com/repos/{owner}/{repo}/contents/{fdir}/_diag_test.json"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    print(f"[diag] GET {api}?ref={branch}")
    r = requests.get(api, headers=headers, params={"ref": branch}, timeout=15)
    print(f"[diag]   -> {r.status_code} {r.text[:200]!r}")
    sha = r.json().get("sha") if r.status_code == 200 else None

    body = {
        "message": "diag test from container",
        "content": base64.b64encode(b'{"diag": true}').decode("ascii"),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha

    print(f"[diag] PUT {api}")
    r = requests.put(api, headers=headers, json=body, timeout=15)
    print(f"[diag]   -> {r.status_code} {r.text[:300]!r}")
    return 0 if r.status_code in (200, 201) else 1


if __name__ == "__main__":
    sys.exit(main())
