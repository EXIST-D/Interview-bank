#!/bin/sh
# Copy the server's newest verified bank backups to this machine, check every archive, keep the newest KEEP.
# Run on your own computer whenever you like (or from launchd/cron):
#   tools/deploy/pull-backups.sh root@<server> <local folder> [bank name, default: every bank]
# The server keeps 14 daily backups on its own disk; this is the copy that survives losing the server.
set -eu
SERVER=${1:?user@server}; DEST=${2:?local folder}; NAME=${3:-}
KEEP=${KEEP:-30}; NEWEST=${NEWEST:-3}
case "$NAME" in *[!A-Za-z0-9._-]*|.*) echo "Bank name: letters, digits, '.', '_' or '-'" >&2; exit 1;; esac
umask 077
names=${NAME:-$(ssh "$SERVER" 'ls -1 /srv/interview-bank/backups')}
sha() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
for bank in $names; do
  case "$bank" in *[!A-Za-z0-9._-]*|.*) continue;; esac
  mkdir -p "$DEST/$bank"
  # Only the newest few: older ones are already here from earlier runs.
  for archive in $(ssh "$SERVER" "ls -1t /srv/interview-bank/backups/$bank/*.zip 2>/dev/null | head -n $NEWEST"); do
    file=$(basename "$archive")
    [ -f "$DEST/$bank/$file" ] && [ -f "$DEST/$bank/$file.sha256" ] && continue
    rsync -t "$SERVER:$archive" "$SERVER:$archive.sha256" "$DEST/$bank/"
    expected=$(cut -d' ' -f1 < "$DEST/$bank/$file.sha256")
    if [ "$(sha "$DEST/$bank/$file")" != "$expected" ]; then
      echo "$bank/$file: checksum mismatch, removed" >&2
      rm -f "$DEST/$bank/$file" "$DEST/$bank/$file.sha256"
      exit 1
    fi
    echo "$bank/$file: copied and verified"
  done
  ls -1t "$DEST/$bank"/*.zip 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do rm -f "$old" "$old.sha256"; done
  echo "$bank: $(ls -1 "$DEST/$bank"/*.zip 2>/dev/null | wc -l | tr -d ' ') backups kept in $DEST/$bank"
done
