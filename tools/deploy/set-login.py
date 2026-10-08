#!/usr/bin/env python3
"""Manage the accounts of a hosted Interview Bank reader. Run it yourself on the server, in a terminal:

    ssh -t root@<server> interview-bank-login add <name> [--bank <bank name>]   # new account (asks for its password)
    ssh -t root@<server> interview-bank-login passwd <name>                      # new password (signs that account out)
    ssh -t root@<server> interview-bank-login remove <name>
    ssh root@<server> interview-bank-login list

Each account reads only /srv/interview-bank/banks/<bank name> (default: the account name); sync.sh fills it.
Passwords are typed here only; the file keeps scrypt hashes. A login file from 1.15 (one account) is upgraded.
"""
import argparse
import getpass
import grp
import json
import os
import subprocess
import sys

SKILL = "/opt/interview-bank/interview-bank/scripts"
LOGIN = "/etc/interview-bank/login"

sys.path.insert(0, SKILL)
from ibank_core.weblogin import load_login, make_user  # noqa: E402


def ask_password(name):
    if not sys.stdin.isatty():
        sys.exit("Run this in an interactive terminal (ssh -t …).")
    password = getpass.getpass(f"Password for {name} (at least 10 characters): ")
    if password != getpass.getpass("Repeat: "):
        sys.exit("Passwords differ.")
    return password


def save(login):
    fd = os.open(LOGIN + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        json.dump(login, out)
    os.chown(LOGIN + ".tmp", 0, grp.getgrnam("ibank").gr_gid)
    os.replace(LOGIN + ".tmp", LOGIN)
    subprocess.run(["systemctl", "restart", "interview-bank-web"], check=True)


parser = argparse.ArgumentParser(description="Accounts of the hosted Interview Bank reader")
sub = parser.add_subparsers(dest="action", required=True)
add = sub.add_parser("add")
add.add_argument("name")
add.add_argument("--bank", help="Bank directory name under /srv/interview-bank/banks (default: the account name)")
sub.add_parser("passwd").add_argument("name")
sub.add_parser("remove").add_argument("name")
sub.add_parser("list")
args = parser.parse_args()

login = load_login(LOGIN) if os.path.exists(LOGIN) else {"schema_version": 2, "users": {}}
users = login["users"]
try:
    if args.action == "list":
        for name, user in sorted(users.items()):
            print(f"{name}\tbank: {user['bank']}")
        sys.exit(0)
    if args.action == "add":
        if args.name in users:
            sys.exit(f"{args.name} exists; use passwd to change its password.")
        users[args.name] = make_user(args.name, ask_password(args.name), args.bank)
        os.makedirs(f"/srv/interview-bank/banks/{users[args.name]['bank']}", exist_ok=True)
    elif args.action == "passwd":
        if args.name not in users:
            sys.exit(f"No account {args.name}.")
        users[args.name] = make_user(args.name, ask_password(args.name), users[args.name]["bank"])
    elif args.action == "remove":
        if users.pop(args.name, None) is None:
            sys.exit(f"No account {args.name}.")
        if not users:
            sys.exit("Keep at least one account (add another first).")
except Exception as exc:  # validation messages name the rule
    sys.exit(str(exc))
save(login)
print(f"Done: {args.action} {args.name}. Accounts: {', '.join(sorted(users))}")
