"""
CLI to manage reviewers in auth_config.yaml.

Usage:
    python manage_auth_users.py init
    python manage_auth_users.py add --username afsuarezg --name "Andres Suarez" --email asuarezg@stanford.edu
    python manage_auth_users.py remove --username afsuarezg
    python manage_auth_users.py list

Passwords are read interactively (never as a CLI arg) and stored as bcrypt
hashes — compatible with streamlit-authenticator. The cookie key is generated
once at `init` and persisted; rotating it logs everyone out.
"""

import argparse
import getpass
import secrets
import sys
from pathlib import Path

import bcrypt
import yaml


CONFIG_PATH = Path("auth_config.yaml")


def _load() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(
            f"{CONFIG_PATH} not found. Run `python manage_auth_users.py init` first."
        )
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)


def _hash_password(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _prompt_password() -> str:
    pw1 = getpass.getpass("Password: ")
    if len(pw1) < 8:
        sys.exit("Password must be at least 8 characters.")
    pw2 = getpass.getpass("Confirm password: ")
    if pw1 != pw2:
        sys.exit("Passwords do not match.")
    return pw1


def cmd_init(_args) -> None:
    if CONFIG_PATH.exists():
        sys.exit(f"{CONFIG_PATH} already exists. Refusing to overwrite.")
    config = {
        "cookie": {
            "name": "notice_review_auth",
            "key": secrets.token_hex(32),
            "expiry_days": 30,
        },
        "credentials": {"usernames": {}},
        "preauthorized": {"emails": []},
    }
    _save(config)
    print(f"Wrote {CONFIG_PATH} with a fresh cookie key.")
    print("Add a user with: python manage_auth_users.py add --username ... --name ... --email ...")


def cmd_add(args) -> None:
    config = _load()
    users = config.setdefault("credentials", {}).setdefault("usernames", {})
    if args.username in users:
        sys.exit(f"User {args.username!r} already exists. Use `remove` first to replace.")
    password = _prompt_password()
    users[args.username] = {
        "email": args.email,
        "name": args.name,
        "password": _hash_password(password),
    }
    _save(config)
    print(f"Added user {args.username!r}.")


def cmd_remove(args) -> None:
    config = _load()
    users = config.get("credentials", {}).get("usernames", {})
    if args.username not in users:
        sys.exit(f"User {args.username!r} not found.")
    del users[args.username]
    _save(config)
    print(f"Removed user {args.username!r}.")


def cmd_list(_args) -> None:
    config = _load()
    users = config.get("credentials", {}).get("usernames", {})
    if not users:
        print("(no users)")
        return
    for username, info in users.items():
        print(f"{username}\t{info.get('name', '')}\t{info.get('email', '')}")


def cmd_passwd(args) -> None:
    config = _load()
    users = config.get("credentials", {}).get("usernames", {})
    if args.username not in users:
        sys.exit(f"User {args.username!r} not found.")
    password = _prompt_password()
    users[args.username]["password"] = _hash_password(password)
    _save(config)
    print(f"Password updated for {args.username!r}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage reviewers in auth_config.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Create auth_config.yaml with a fresh cookie key").set_defaults(func=cmd_init)

    p_add = sub.add_parser("add", help="Add a user")
    p_add.add_argument("--username", required=True)
    p_add.add_argument("--name", required=True, help="Display name")
    p_add.add_argument("--email", required=True)
    p_add.set_defaults(func=cmd_add)

    p_rm = sub.add_parser("remove", help="Remove a user")
    p_rm.add_argument("--username", required=True)
    p_rm.set_defaults(func=cmd_remove)

    sub.add_parser("list", help="List users").set_defaults(func=cmd_list)

    p_pw = sub.add_parser("passwd", help="Reset a user's password")
    p_pw.add_argument("--username", required=True)
    p_pw.set_defaults(func=cmd_passwd)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
