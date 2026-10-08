#!/bin/sh
# Copy a bank's canonical data to one account on the server (read-only reader there).
# Run on the machine where the agent works:
#   tools/deploy/sync.sh <bank directory> root@<server> <bank name of the account, e.g. its username>
# Only data/, config.json and manifest.json are sent: no images, runs, caches or exports.
set -eu
BANK=${1:?bank directory}; SERVER=${2:?user@server}; NAME=${3:?bank name of the account on the server}
case "$NAME" in *[!A-Za-z0-9._-]*|.*|'') echo "Bank name: letters, digits, '.', '_' or '-'" >&2; exit 1;; esac
[ -f "$BANK/manifest.json" ] && [ -d "$BANK/data" ] || { echo "$BANK is not a bank" >&2; exit 1; }
ssh "$SERVER" "install -d -o ibank -g ibank -m 750 /srv/interview-bank/banks/$NAME"
# macOS ships an rsync without --chmod, so permissions are set on the server afterwards.
rsync -rlt --delete "$BANK/data" "$BANK/config.json" "$BANK/manifest.json" "$SERVER:/srv/interview-bank/banks/$NAME/"
ssh "$SERVER" "chown -R ibank:ibank /srv/interview-bank/banks/$NAME && chmod -R u=rwX,g=rX,o= /srv/interview-bank/banks/$NAME"
echo "Synced $BANK to $SERVER (bank $NAME)"
