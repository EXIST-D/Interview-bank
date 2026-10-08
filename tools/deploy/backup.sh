#!/bin/sh
# Daily verified backup of every hosted bank (run by interview-bank-backup.service as user ibank).
# Archives go to /srv/interview-bank/backups/<bank>/; the newest KEEP are kept.
set -eu
umask 077
KEEP=${KEEP:-14}
CLI=/opt/interview-bank/interview-bank/scripts/ibank.py
for BANK in /srv/interview-bank/banks/*/; do
  NAME=$(basename "$BANK")
  [ -f "$BANK/manifest.json" ] || continue
  OUT=/srv/interview-bank/backups/$NAME
  install -d -m 750 "$OUT"
  ARCHIVE=$(python3 -B "$CLI" --bank "$BANK" --json backup create | python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["archive"])')
  python3 -B "$CLI" --bank "$BANK" --json backup verify --archive "$ARCHIVE" > /dev/null
  mv "$ARCHIVE" "$ARCHIVE.sha256" "$OUT/"
  ls -1t "$OUT"/*.zip | tail -n +$((KEEP + 1)) | while read -r OLD; do rm -f "$OLD" "$OLD.sha256"; done
  echo "$NAME: $(basename "$ARCHIVE") verified, $(ls -1 "$OUT"/*.zip | wc -l) kept"
done
