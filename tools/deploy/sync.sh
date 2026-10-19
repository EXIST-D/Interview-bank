#!/bin/sh
# Copy a bank's canonical data to one account on the server (read-only reader there).
# Run on the machine where the agent works:
#   tools/deploy/sync.sh [--force] <bank directory> root@<server> <bank name of the account, e.g. its username>
# Only data/, collections/ (八股 notes and links), config.json and manifest.json are sent: no images, runs, caches or exports.
# The server's personal/ (your own answers, favourites and learning state) is never sent or deleted.
# When the server holds newer data than this bank (the agent worked there), the copy is refused unless --force.
set -eu
FORCE=0
if [ "${1:-}" = "--force" ]; then FORCE=1; shift; fi
BANK=${1:?bank directory}; SERVER=${2:?user@server}; NAME=${3:?bank name of the account on the server}
case "$NAME" in *[!A-Za-z0-9._-]*|.*|'') echo "Bank name: letters, digits, '.', '_' or '-'" >&2; exit 1;; esac
[ -f "$BANK/manifest.json" ] && [ -d "$BANK/data" ] || { echo "$BANK is not a bank" >&2; exit 1; }
NEWEST='import os,sys
paths=[p for p in ("manifest.json","config.json") if os.path.isfile(p)]
for d in ("data","collections"):
    for root,_,files in os.walk(d): paths += [os.path.join(root,f) for f in files]
print(int(max([os.stat(p).st_mtime for p in paths] or [0])))'
here=$(cd "$BANK" && python3 -c "$NEWEST")
there=$(ssh "$SERVER" "cd /srv/interview-bank/banks/$NAME 2>/dev/null && python3 -c '$NEWEST' || echo 0")
if [ "$there" -gt "$here" ] && [ "$FORCE" -ne 1 ]; then
  echo "The server's bank $NAME changed after this one ($(date -r "$there" 2>/dev/null || echo "$there") vs local)." >&2
  echo "Copy it here first (or back it up), or pass --force to overwrite the server." >&2
  exit 1
fi
ssh "$SERVER" "install -d -o ibank -g ibank -m 750 /srv/interview-bank/banks/$NAME"
# macOS ships an rsync without --chmod, so permissions are set on the server afterwards.
set -- "$BANK/data" "$BANK/config.json" "$BANK/manifest.json"
if [ -d "$BANK/collections" ]; then set -- "$@" "$BANK/collections"; fi
rsync -rlt --delete "$@" "$SERVER:/srv/interview-bank/banks/$NAME/"
ssh "$SERVER" "chown -R ibank:ibank /srv/interview-bank/banks/$NAME && chmod -R u=rwX,g=rX,o= /srv/interview-bank/banks/$NAME"
echo "Synced $BANK to $SERVER (bank $NAME)"
