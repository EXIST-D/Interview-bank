#!/usr/bin/env python3
"""Set the one login of a hosted Interview Bank reader. Run it yourself on the server, in a terminal:

    ssh -t root@<server> interview-bank-login

The password is typed here only; the file keeps an scrypt hash. Every device is signed out afterwards.
"""
import getpass
import grp
import json
import os
import subprocess
import sys

SKILL = "/opt/interview-bank/interview-bank/scripts"
LOGIN = "/etc/interview-bank/login"

sys.path.insert(0, SKILL)
from ibank_core.weblogin import make_login  # noqa: E402

if not sys.stdin.isatty():
    sys.exit("Run this in an interactive terminal (ssh -t …).")
username = input("Username: ").strip()
password = getpass.getpass("Password (at least 10 characters): ")
if password != getpass.getpass("Repeat: "):
    sys.exit("Passwords differ.")
try:
    login = make_login(username, password)
except Exception as exc:  # the validation message names the rule
    sys.exit(str(exc))
fd = os.open(LOGIN + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)
with os.fdopen(fd, "w", encoding="utf-8") as out:
    json.dump(login, out)
os.chown(LOGIN + ".tmp", 0, grp.getgrnam("ibank").gr_gid)
os.replace(LOGIN + ".tmp", LOGIN)
subprocess.run(["systemctl", "restart", "interview-bank-web"], check=True)
print(f"Login set for {username}. Open your site's /ibank/ page and sign in.")
