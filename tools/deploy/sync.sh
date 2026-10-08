#!/bin/sh
# Copy a bank's canonical data to the server (read-only reader there). Run on the machine where the agent works.
#   tools/deploy/sync.sh <bank directory> root@<server>
# Only data/, config.json and manifest.json are sent: no images, runs, caches or exports.
set -eu
BANK=${1:?bank directory}; SERVER=${2:?user@server}
[ -f "$BANK/manifest.json" ] && [ -d "$BANK/data" ] || { echo "$BANK is not a bank" >&2; exit 1; }
# macOS ships an rsync without --chmod, so permissions are set on the server afterwards.
rsync -rlt --delete "$BANK/data" "$BANK/config.json" "$BANK/manifest.json" "$SERVER:/srv/interview-bank/bank/"
ssh "$SERVER" 'chown -R ibank:ibank /srv/interview-bank/bank && chmod -R u=rwX,g=rX,o= /srv/interview-bank/bank'
echo "Synced $BANK to $SERVER"
